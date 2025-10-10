import sys
import os
import MCP.mcp

# Add project root to sys.path to ensure MCP module can be found
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Forcing MCP to be relative to LANGGRAPH_MCP if this script is run from within LANGGRAPH_MCP
# This also helps if LANGGRAPH_MCP is the current working directory.
current_script_dir = os.path.dirname(os.path.abspath(__file__))
if "LANGGRAPH_MCP" in current_script_dir.split(os.sep):
    # Assumes MCP is a direct subdirectory of LANGGRAPH_MCP
    mcp_module_path = os.path.join(current_script_dir, "..") 
    # Normalize and add, this handles if script is in LANGGRAPH_MCP or subfolder
    potential_project_root = os.path.normpath(os.path.join(os.path.dirname(__file__))) 
    if os.path.basename(potential_project_root) == "LANGGRAPH_MCP" and potential_project_root not in sys.path:
        sys.path.insert(0, potential_project_root)
    elif os.path.basename(os.path.dirname(potential_project_root)) == "LANGGRAPH_MCP" and os.path.dirname(potential_project_root) not in sys.path:
         sys.path.insert(0, os.path.dirname(potential_project_root))

from flask import Flask, request, jsonify, render_template

from MCP.mcp import MCP
from nos_langgraph.nodes import create_langgraph_workflow
import traceback
import time
import uuid
from pathlib import Path
import threading

# Importar o módulo de logging unificado
from common_logger import get_app_logger

# Configure logging usando o sistema unificado
logger = get_app_logger()

# Configurar Flask para servir arquivos estáticos e templates
app = Flask(__name__,
            static_url_path='/static',
            static_folder='static',
            template_folder='templates')

# Global state
mcp_instances = {}

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Erro ao renderizar template: {str(e)}")
        return "Erro ao carregar a interface. Verifique os logs para mais detalhes.", 500

@app.route('/dashboard')
def dashboard():
    try:
        return render_template('dashboard.html')
    except Exception as e:
        logger.error(f"Erro ao renderizar dashboard: {str(e)}")
        return f"Erro ao carregar o dashboard: {str(e)}", 500

@app.route('/api/start', methods=['POST'])
def start_pipeline():
    try:
        story_text = None
        
        # Log request information
        logger.info(f"Received request - Content-Type: {request.content_type}")
        logger.info(f"Form data: {request.form}")
        logger.info(f"Files: {request.files}")
        
        # Handle JSON data
        if request.is_json:
            logger.info("Processing JSON request")
            data = request.get_json()
            story_text = data.get('story_text')
            logger.info(f"Received story text from JSON: {story_text[:100]}...")
            
        # Handle form data
        elif request.form:
            logger.info("Processing form data")
            story_text = request.form.get('story_text')
            logger.info(f"Received story text from form: {story_text[:100] if story_text else None}...")
            
        # Handle file upload
        if not story_text and request.files:
            logger.info("Processing file upload")
            if 'story_file' in request.files:
                file = request.files['story_file']
                if file and file.filename.endswith('.txt'):
                    story_text = file.read().decode('utf-8')
                    logger.info(f"Read story text from file: {story_text[:100]}...")
        
        if not story_text:
            logger.error("No story text provided")
            return jsonify({
                'error': 'História é obrigatória. Por favor, forneça um texto ou arquivo.'
            }), 400
            
        # Initialize MCP
        session_id = str(uuid.uuid4())
        mcp = MCP(session_id=session_id)
        mcp_instances[session_id] = mcp
        
        # Log the received story
        mcp.log_status("system", f"História recebida com {len(story_text)} caracteres")
        logger.info(f"Created session {session_id} for story with {len(story_text)} characters")
        
        # Initialize state
        base_output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(base_output_dir, exist_ok=True)
        
        # Align initial_state with AgentState fields
        # Fields like output_dir, generate_images etc. need to be added to AgentState 
        # if they are to be part of the graph's state.
        # For now, only passing fields defined in AgentState or that AgentState can accept via mcp.
        initial_state_data = {
            "initial_story": story_text,
            "current_task_id": str(uuid.uuid4()), # Matches AgentState.current_task_id
            "mcp": mcp,                         # Matches AgentState.mcp
            # "output_dir": base_output_dir, # Not directly in AgentState, manage via mcp or node logic
            # "generate_images": True,       # These are control flags, perhaps should be part of a config dict within AgentState
            # "generate_animations": True,
            # "generate_audio": True,
            # "generate_video": True,
            # "use_cache": False             # AgentState has cache_dir and handles its cache object
            # Add other fields if they are explicitly defined in AgentState and needed at init
        }
        
        # Start pipeline in a separate thread
        def run_pipeline():
            try:
                workflow_graph = create_langgraph_workflow()
                app = workflow_graph.compile()
                
                logger.info(f"Starting pipeline stream for session {session_id} with initial state keys: {list(initial_state_data.keys())}")
                
                final_stream_output = None
                # Pass the corrected initial_state_data
                for chunk in app.stream(initial_state_data):
                    if chunk:
                        for node_name_in_chunk, state_after_node in chunk.items():
                            logger.debug(f"Stream chunk for session {session_id}: Node [{node_name_in_chunk}] output generated.")
                    final_stream_output = chunk
                
                logger.info(f"Pipeline stream finished for session {session_id}.")

                if mcp.context.get("errors"):
                    error_summary = "; ".join([err.get('error', 'Unknown error') for err in mcp.context["errors"]])
                    detailed_error_msg = f"Pipeline falhou com erros registrados no MCP: {error_summary}"
                    mcp.log_error("system", detailed_error_msg)
                    logger.error(detailed_error_msg)
                else:
                    success_msg = "Pipeline concluído com sucesso (stream finalizado sem erros no MCP)."
                    mcp.log_status("system", success_msg)
                    logger.info(success_msg)
                
            except Exception as e:
                critical_error_msg = f"Erro crítico na execução do pipeline: {str(e)}"
                mcp.log_error("system", critical_error_msg)
                logger.error(critical_error_msg)
                logger.error(traceback.format_exc())
        
        threading.Thread(target=run_pipeline, daemon=True).start()
        
        return jsonify({
            "status": "iniciado",
            "session_id": session_id
        })
        
    except Exception as e:
        logger.error(f"Error starting pipeline endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": str(e)
        }), 500

@app.route('/api/status/<session_id>')
def get_status(session_id):
    try:
        if session_id not in mcp_instances:
            return jsonify({
                "error": "Session not found"
            }), 404
            
        mcp = mcp_instances[session_id]
        status = mcp.get_status()
        metrics = mcp.get_metrics()
        
        return jsonify({
            "status": status,
            "metrics": metrics,
            "session_id": session_id
        })
        
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return jsonify({
            "error": str(e)
        }), 500

@app.route('/api/logs/<session_id>')
def get_logs(session_id):
    try:
        if session_id not in mcp_instances:
            return jsonify({
                "error": "Session not found"
            }), 404
            
        mcp = mcp_instances[session_id]
        logs = mcp.get_logs()
        
        return jsonify({
            "logs": logs,
            "session_id": session_id
        })
        
    except Exception as e:
        logger.error(f"Error getting logs: {str(e)}")
        return jsonify({
            "error": str(e)
        }), 500

@app.route('/api/stop/<session_id>')
def stop_pipeline(session_id):
    try:
        if session_id not in mcp_instances:
            return jsonify({
                "error": "Session not found"
            }), 404
            
        mcp = mcp_instances[session_id]
        mcp.stop()
        del mcp_instances[session_id]
        
        return jsonify({
            "status": "stopped",
            "session_id": session_id
        })
        
    except Exception as e:
        logger.error(f"Error stopping pipeline: {str(e)}")
        return jsonify({
            "error": str(e)
        }), 500

@app.route('/api/sessions')
def get_sessions():
    try:
        sessions = [{"id": session_id, "status": mcp.get_status()} for session_id, mcp in mcp_instances.items()]
        return jsonify({
            "sessions": sessions
        })
    except Exception as e:
        logger.error(f"Erro ao listar sessões: {str(e)}")
        return jsonify({
            "error": str(e)
        }), 500

@app.route('/api/progress/<session_id>')
def get_progress(session_id):
    try:
        if session_id not in mcp_instances:
            return jsonify({
                "error": "Session not found"
            }), 404
            
        mcp = mcp_instances[session_id]
        status = mcp.get_status()
        metrics = mcp.get_metrics()
        logs = mcp.get_logs()
        
        # Obter informações de nós
        nodes = []
        node_names = ["script_processor", "script_analysis", "scene_generation", 
                     "animation_generation", "audio_generation", "synchronize_assets", 
                     "video_composition", "youtube_upload", "end"]
        
        for node_name in node_names:
            node_status = "WAITING"
            node_message = ""
            node_error = ""
            
            # Verificar se o nó tem status
            if node_name in mcp.context.get("status", {}):
                node_message = mcp.context["status"][node_name]
                node_status = "COMPLETE" if "Completed" in node_message else "RUNNING"
            
            # Verificar erros do nó
            for error in mcp.context.get("errors", []):
                if error.get("node") == node_name:
                    node_status = "ERROR"
                    node_error = error.get("error", "")
            
            nodes.append({
                "name": node_name,
                "status": node_status,
                "message": node_message,
                "error": node_error
            })
        
        # Coletar informações sobre animações geradas
        animations = []
        audios = []
        final_video = None
        
        # Verificar se temos dados sobre animações no contexto do MCP
        if "animated_scene_paths" in mcp.context.get("resources", {}):
            animated_paths = mcp.context["resources"]["animated_scene_paths"]
            for i, path in enumerate(animated_paths):
                animations.append({
                    "scene_number": i+1,
                    "path": os.path.relpath(path, os.path.join(os.path.dirname(__file__), "static")),
                    "simulated": not os.path.getsize(path) > 1024  # Considerar simulado se menor que 1KB
                })
        
        # Verificar se temos dados sobre áudios no contexto do MCP
        if "audio_paths" in mcp.context.get("resources", {}):
            audio_info = mcp.context["resources"]["audio_paths"]
            for audio in audio_info:
                path = audio.get("path", "")
                audios.append({
                    "scene_number": audio.get("scene_number", 0),
                    "path": os.path.relpath(path, os.path.join(os.path.dirname(__file__), "static")),
                    "text": audio.get("text", ""),
                    "simulated": audio.get("simulated", False) or not os.path.getsize(path) > 1024
                })
        
        # Verificar se temos o vídeo final
        if "final_video_path" in mcp.context.get("resources", {}):
            video_path = mcp.context["resources"]["final_video_path"]
            if os.path.exists(video_path):
                final_video = {
                    "path": os.path.relpath(video_path, os.path.join(os.path.dirname(__file__), "static")),
                    "title": mcp.context["resources"].get("video_title", "Vídeo Final")
                }
        
        return jsonify({
            "status": status,
            "metrics": metrics,
            "logs": logs,
            "nodes": nodes,
            "animations": animations,
            "audios": audios,
            "final_video": final_video,
            "session_id": session_id
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter progresso: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            "error": str(e)
        }), 500

if __name__ == '__main__':
    # Configurar variáveis de ambiente
    os.environ['FLASK_APP'] = 'run_mcp:app'
    os.environ['FLASK_ENV'] = 'development'
    
    # Configurar Flask para modo de desenvolvimento
    app.config['ENV'] = 'development'
    app.config['DEBUG'] = True
    app.config['TESTING'] = True
    
    # Iniciar o servidor
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)