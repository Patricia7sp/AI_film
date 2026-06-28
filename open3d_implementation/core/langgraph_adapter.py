"""
LangGraph Adapter for Open3D Implementation
Integrates LangGraph workflows with Open3D visualization
"""

from typing import Dict, Any, TypedDict, List
from dataclasses import dataclass


class Open3DAgentState(TypedDict):
    """State for Open3D Agent workflow"""
    messages: List[str]
    current_step: str
    scene_data: Dict[str, Any]
    generated_content: Dict[str, Any]
    # Campos adicionais necessários
    story_text: str
    session_id: str
    input_type: str
    max_scenes: int
    enhanced_multimodal_input_asset: Dict[str, Any]


def create_open3d_workflow():
    """
    Creates a LangGraph workflow for Open3D processing
    
    Returns:
        A configured LangGraph workflow
    """
    try:
        from langgraph.graph import StateGraph, END
        from orchestration.llm_config import get_llm, generate_cinematic_prompt
        import json
        import os
        
        print("🔧 Criando workflow LangGraph funcional...")
        
        def extract_story(state: Open3DAgentState) -> Open3DAgentState:
            """Extract and process story from multimodal input"""
            # Debug: ver o que está no state
            print(f"🔍 DEBUG - State keys: {list(state.keys())}")
            print(f"🔍 DEBUG - State type: {type(state)}")
            
            story_text = state.get('story_text', '')
            
            if not story_text:
                # Try to get from enhanced_multimodal_input_asset
                if 'enhanced_multimodal_input_asset' in state:
                    print(f"🔍 DEBUG - Found enhanced_multimodal_input_asset in state")
                    story_text = state['enhanced_multimodal_input_asset'].get('story_text', '')
                else:
                    print(f"⚠️ DEBUG - enhanced_multimodal_input_asset NOT in state")
            
            print(f"📖 Processando história: {len(story_text)} caracteres")
            
            if not story_text:
                print(f"⚠️ AVISO: História vazia! State completo: {state}")
            
            # Generate cinematic prompt using Flash model (Pro exceeded quota)
            llm = get_llm()
            prompt = generate_cinematic_prompt(story_text, use_pro_model=False)
            
            state.update({
                'story_text': story_text,
                'cinematic_prompt': prompt,
                'current_step': 'story_extracted'
            })
            
            return state
        
        def generate_scenes(state: Open3DAgentState) -> Open3DAgentState:
            """Generate scenes from story using LLM"""
            story_text = state.get('story_text', '')
            cinematic_prompt = state.get('cinematic_prompt', '')
            max_scenes = state.get('max_scenes', 8)
            
            print("🎬 Gerando cenas...")
            
            if not story_text:
                print("⚠️ História vazia, usando cenas mock")
                scenes = [
                    {"scene_id": 1, "description": "Mock scene", "prompt": cinematic_prompt, "duration": 5},
                    {"scene_id": 2, "description": "Mock scene", "prompt": cinematic_prompt, "duration": 5},
                    {"scene_id": 3, "description": "Mock scene", "prompt": cinematic_prompt, "duration": 5}
                ]
            else:
                # Generate real scenes using LLM
                try:
                    llm = get_llm()
                    
                    scene_prompt = f"""
Divida esta história em {max_scenes} cenas cinematográficas.

HISTÓRIA:
{story_text}

Para cada cena, forneça:
1. ID da cena (número)
2. Descrição detalhada (2-3 frases)
3. Prompt visual para geração de imagem (estilo cinematográfico)
4. Duração sugerida (5-10 segundos)

Retorne em formato JSON:
[
  {{"scene_id": 1, "description": "...", "prompt": "...", "duration": 6}},
  ...
]
"""
                    
                    response = llm.invoke(scene_prompt)
                    
                    # Parse response
                    import json
                    import re
                    import ast
                    
                    # Extrair conteúdo da resposta - tratar diferentes formatos
                    raw_content = response.content if hasattr(response, 'content') else str(response)
                    
                    # Debug: ver tipo e conteúdo original
                    print(f"🔍 DEBUG - Tipo de raw_content: {type(raw_content)}")
                    print(f"🔍 DEBUG - raw_content (primeiros 200 chars): {str(raw_content)[:200]}")
                    
                    # Verificar se é um dicionário real ou string que parece dict
                    if isinstance(raw_content, dict):
                        content = raw_content.get('text', str(raw_content))
                    elif isinstance(raw_content, list):
                        content = " ".join(str(item) for item in raw_content)
                    else:
                        # É string - verificar se parece um dict
                        content_str = str(raw_content)
                        
                        # Tentar extrair valor de 'text' se a string parecer um dict
                        if "{'type': 'text', 'text':" in content_str or '{"type": "text", "text":' in content_str:
                            try:
                                # Tentar parse como dict Python
                                parsed = ast.literal_eval(content_str)
                                if isinstance(parsed, dict) and 'text' in parsed:
                                    content = parsed['text']
                                    print(f"✅ Extraído campo 'text' do dict")
                                else:
                                    content = content_str
                            except:
                                # Fallback: regex para extrair texto
                                text_match = re.search(r"'text':\s*['\"](.+?)['\"]", content_str, re.DOTALL)
                                if text_match:
                                    content = text_match.group(1)
                                    print(f"✅ Extraído campo 'text' via regex")
                                else:
                                    content = content_str
                        else:
                            content = content_str
                    
                    # Debug: ver resposta do LLM processada
                    print(f"🔍 DEBUG - Resposta LLM processada (primeiros 500 chars): {content[:500]}")
                    
                    # Extract JSON from response - melhorar regex para markdown
                    # Remover markdown se presente
                    content = content.replace('```json', '').replace('```', '').strip()
                    
                    # Procurar por array JSON
                    json_match = re.search(r'\[\s*\{.*?\}\s*\]', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group()
                        # Limpar possíveis problemas
                        json_str = json_str.replace('{{', '{').replace('}}', '}')
                        # Remover aspas extras se presentes
                        json_str = json_str.replace('"[{', '[{').replace('}]"', '}]')
                        
                        try:
                            scenes = json.loads(json_str)
                            print(f"✅ {len(scenes)} cenas geradas com LLM")
                        except json.JSONDecodeError as e:
                            print(f"⚠️ Erro no JSON: {e}")
                            print(f"🔍 JSON tentado: {json_str[:200]}...")
                            raise ValueError("JSON inválido mesmo após limpeza")
                    else:
                        print(f"🔍 Conteúdo completo (primeiros 1000 chars): {content[:1000]}")
                        raise ValueError("Não foi possível extrair JSON da resposta")
                        
                except Exception as e:
                    print(f"⚠️ Erro ao gerar cenas com LLM: {e}")
                    print("💡 Usando cenas baseadas na história")
                    # Fallback: criar cenas simples baseadas na história
                    scenes = []
                    story_parts = story_text.split('\n\n')[:max_scenes]
                    for i, part in enumerate(story_parts, 1):
                        scenes.append({
                            "scene_id": i,
                            "description": part[:200],
                            "prompt": f"{cinematic_prompt}, scene showing: {part[:100]}",
                            "duration": 6
                        })
                    print(f"✅ {len(scenes)} cenas criadas (fallback)")
            
            state.update({
                'scenes': scenes,
                'scenes_count': len(scenes),
                'current_step': 'scenes_generated'
            })
            
            print(f"✅ {len(scenes)} cenas geradas")
            return state
        
        def generate_images(state: Open3DAgentState) -> Open3DAgentState:
            """Generate images for scenes using ComfyUI on a RunPod Serverless endpoint"""
            scenes = state.get('scenes', [])
            runpod_api_key = os.getenv('RUNPOD_API_KEY', '')
            runpod_endpoint_id = os.getenv('RUNPOD_ENDPOINT_ID', '')

            print("🖼️ Gerando imagens com ComfyUI (RunPod Serverless)...")

            scene_images = []

            for i, scene in enumerate(scenes[:3]):  # Limit to 3 scenes
                try:
                    print(f"🎨 Gerando imagem para cena {scene['scene_id']}...")

                    # Create output directory
                    os.makedirs('output', exist_ok=True)
                    image_path = f"output/scene_{scene['scene_id']}_image.png"

                    # Generate image using ComfyUI via RunPod Serverless
                    if runpod_api_key and runpod_endpoint_id:
                        import requests
                        import time
                        import base64

                        run_url = f"https://api.runpod.ai/v2/{runpod_endpoint_id}/run"
                        status_url_template = f"https://api.runpod.ai/v2/{runpod_endpoint_id}/status/{{job_id}}"
                        headers = {"Authorization": f"Bearer {runpod_api_key}"}

                        # Workflow no formato "API" do ComfyUI (Workflow > Export (API))
                        workflow = {
                            "1": {
                                "inputs": {
                                    "text": scene['prompt'],
                                    "clip": ["4", 1]
                                },
                                "class_type": "CLIPTextEncode"
                            },
                            "2": {
                                "inputs": {
                                    "text": "blurry, bad quality, distorted",
                                    "clip": ["4", 1]
                                },
                                "class_type": "CLIPTextEncode"
                            },
                            "3": {
                                "inputs": {
                                    "seed": 123456789,
                                    "steps": 20,
                                    "cfg": 7,
                                    "sampler_name": "euler",
                                    "scheduler": "normal",
                                    "denoise": 1,
                                    "model": ["4", 0],
                                    "positive": ["1", 0],
                                    "negative": ["2", 0],
                                    "latent_image": ["5", 0]
                                },
                                "class_type": "KSampler"
                            },
                            "4": {
                                "inputs": {
                                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                                },
                                "class_type": "CheckpointLoaderSimple"
                            },
                            "5": {
                                "inputs": {
                                    "width": 512,
                                    "height": 512,
                                    "batch_size": 1
                                },
                                "class_type": "EmptyLatentImage"
                            },
                            "6": {
                                "inputs": {
                                    "samples": ["3", 0],
                                    "vae": ["4", 2]
                                },
                                "class_type": "VAEDecode"
                            },
                            "7": {
                                "inputs": {
                                    "filename_prefix": f"scene_{scene['scene_id']}",
                                    "images": ["6", 0]
                                },
                                "class_type": "SaveImage"
                            }
                        }

                        print("📤 Enviando job para o endpoint RunPod Serverless...")
                        response = requests.post(
                            run_url,
                            json={"input": {"workflow": workflow}},
                            headers=headers,
                            timeout=30,
                        )

                        if response.status_code == 200:
                            job_id = response.json().get('id')
                            print(f"🆔 Job ID: {job_id}")

                            # Poll status: worker escala de zero, então o cold start pode levar
                            # de alguns segundos a ~1 minuto além do tempo de geração em si.
                            max_wait = 180
                            wait_time = 0
                            while wait_time < max_wait:
                                time.sleep(3)
                                wait_time += 3

                                status_response = requests.get(
                                    status_url_template.format(job_id=job_id),
                                    headers=headers,
                                    timeout=10,
                                )
                                if status_response.status_code != 200:
                                    print(f"⚠️ Erro ao consultar status: {status_response.status_code}")
                                    continue

                                status_payload = status_response.json()
                                job_status = status_payload.get('status')

                                if job_status == 'COMPLETED':
                                    images = status_payload.get('output', {}).get('images', [])
                                    if images:
                                        image_b64 = images[0].get('data', '')
                                        with open(image_path, 'wb') as f:
                                            f.write(base64.b64decode(image_b64))

                                        if os.path.exists(image_path) and os.path.getsize(image_path) > 1000:
                                            scene_images.append({
                                                'scene_id': scene['scene_id'],
                                                'image_path': image_path,
                                                'prompt': scene['prompt'],
                                                'runpod_job_id': job_id,
                                                'generation_method': 'comfyui'
                                            })
                                            print(f"✅ Imagem ComfyUI REAL gerada: cena {scene['scene_id']} ({os.path.getsize(image_path)} bytes)")
                                        else:
                                            print("⚠️ Arquivo decodificado não é uma imagem válida")
                                    else:
                                        print("⚠️ Job concluído sem imagens no output")
                                    break
                                elif job_status in ('FAILED', 'CANCELLED', 'TIMED_OUT'):
                                    print(f"⚠️ Job RunPod terminou com status: {job_status} — {status_payload.get('error')}")
                                    break
                                else:
                                    print(f"⏳ Status: {job_status} ({wait_time}s)")
                            else:
                                print(f"⏱️ Timeout após {max_wait}s aguardando o job RunPod")
                        else:
                            print(f"⚠️ Erro ao enviar job: {response.status_code} - {response.text}")

                    # Verifica se a imagem já foi gerada com sucesso acima; se não, cai no mock
                    if any(img['scene_id'] == scene['scene_id'] and img['generation_method'] == 'comfyui' for img in scene_images):
                        continue

                    # Fallback mock generation se ComfyUI falhar
                    print(f"💡 Usando mock de imagem para cena {scene['scene_id']}")
                    with open(image_path, 'w') as f:
                        f.write(f"Mock image for scene {scene['scene_id']}: {scene['prompt']}")
                    
                    scene_images.append({
                        'scene_id': scene['scene_id'],
                        'image_path': image_path,
                        'prompt': scene['prompt'],
                        'generation_method': 'mock'
                    })
                    
                    print(f"✅ Imagem gerada (mock): cena {scene['scene_id']}")
                    
                except Exception as e:
                    print(f"⚠️ Erro ao gerar imagem para cena {scene['scene_id']}: {e}")
                    # Continue with next scene
            
            state.update({
                'scene_images': scene_images,
                'images_count': len(scene_images),
                'current_step': 'images_generated'
            })
            
            return state
        
        def generate_audio(state: Open3DAgentState) -> Open3DAgentState:
            """Generate audio narration using ElevenLabs"""
            story_text = state.get('story_text', '')
            scenes = state.get('scenes', [])
            
            print("🎙️ Gerando áudio com ElevenLabs...")
            
            audio_files = []
            
            for i, scene in enumerate(scenes[:3]):  # Limit to 3 scenes
                try:
                    print(f"🎤 Gerando áudio para cena {scene['scene_id']}...")
                    
                    # Create output directory
                    os.makedirs('output', exist_ok=True)
                    audio_path = f"output/scene_{scene['scene_id']}_audio.mp3"
                    
                    # Generate audio using ElevenLabs
                    elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY')
                    
                    if elevenlabs_api_key:
                        import requests
                        import json
                        
                        print(f"🔑 ElevenLabs API Key: {'✅ Configurada' if elevenlabs_api_key else '❌ Não encontrada'}")
                        
                        # Prepare text for narration (scene description)
                        narration_text = f"Cena {scene['scene_id']}: {scene['description']}"
                        print(f"📝 Texto para narração: {narration_text[:100]}...")
                        
                        # ElevenLabs API call
                        headers = {
                            'Accept': 'audio/mpeg',
                            'Content-Type': 'application/json',
                            'xi-api-key': elevenlabs_api_key
                        }
                        
                        data = {
                            'text': narration_text,
                            'model_id': 'eleven_multilingual_v2',  # Supports multiple languages
                            'voice_settings': {
                                'stability': 0.5,
                                'similarity_boost': 0.5
                            }
                        }
                        
                        # Use a default voice (you can customize this)
                        voice_url = 'https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM'
                        
                        print(f"🎤 Chamando ElevenLabs API...")
                        try:
                            response = requests.post(voice_url, headers=headers, json=data, timeout=30)
                            
                            print(f"📊 Status Code: {response.status_code}")
                            if response.status_code != 200:
                                print(f"❌ Resposta ElevenLabs: {response.text[:500]}")
                            
                            if response.status_code == 200:
                                # Save real audio
                                with open(audio_path, 'wb') as f:
                                    f.write(response.content)
                                
                                # Verify it's real audio
                                if os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
                                    audio_files.append({
                                        'scene_id': scene['scene_id'],
                                        'audio_path': audio_path,
                                        'text': narration_text,
                                        'voice_id': '21m00Tcm4TlvDq8ikWAM',
                                        'generation_method': 'elevenlabs'
                                    })
                                    
                                    print(f"✅ Áudio ElevenLabs REAL gerado: cena {scene['scene_id']} ({os.path.getsize(audio_path)} bytes)")
                                    continue
                                else:
                                    print(f"⚠️ Arquivo de áudio não é válido")
                            else:
                                print(f"⚠️ ElevenLabs falhou: HTTP {response.status_code}")
                                if response.status_code == 401:
                                    print(f"❌ Erro de autenticação - verifique API Key")
                                elif response.status_code == 429:
                                    print(f"⚠️ Limite de taxa excedido - tente novamente mais tarde")
                                elif response.status_code == 400:
                                    print(f"❌ Requisição inválida - verifique os parâmetros")
                                    
                        except Exception as e:
                            print(f"⚠️ Erro na chamada ElevenLabs: {e}")
                    else:
                        print(f"❌ ElevenLabs API Key não encontrada nas variáveis de ambiente")
                    
                    # Fallback mock generation
                    with open(audio_path, 'w') as f:
                        f.write(f"Mock audio: {narration_text}")
                    
                    audio_files.append({
                        'scene_id': scene['scene_id'],
                        'audio_path': audio_path,
                        'text': narration_text,
                        'generation_method': 'mock'
                    })
                    
                    print(f"✅ Áudio gerado (mock): cena {scene['scene_id']}")
                    
                except Exception as e:
                    print(f"⚠️ Erro ao gerar áudio para cena {scene['scene_id']}: {e}")
                    # Continue with next scene
            
            state.update({
                'audio_files': audio_files,
                'audio_count': len(audio_files),
                'current_step': 'audio_generated'
            })
            
            print(f"✅ {len(audio_files)} áudios gerados")
            return state
        
        def compile_video(state: Open3DAgentState) -> Open3DAgentState:
            """Compile final video using FFmpeg"""
            scene_images = state.get('scene_images', [])
            audio_files = state.get('audio_files', [])
            
            print("🎬 Compilando vídeo final com FFmpeg...")
            
            video_path = 'output/final_video.mp4'
            
            try:
                import subprocess
                import os
                
                # Create output directory
                os.makedirs('output', exist_ok=True)
                
                # Check if FFmpeg is available
                try:
                    subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                    ffmpeg_available = True
                except (subprocess.CalledProcessError, FileNotFoundError):
                    ffmpeg_available = False
                    print("⚠️ FFmpeg não disponível, usando mock")
                
                if ffmpeg_available and scene_images:
                    print("🔧 Usando FFmpeg real para compilação...")
                    
                    # Create a temporary file list for FFmpeg
                    filelist_path = 'output/filelist.txt'
                    with open(filelist_path, 'w') as f:
                        for img in scene_images:
                            # Check if it's a real image file (not mock)
                            img_path = img['image_path']
                            if os.path.exists(img_path) and os.path.getsize(img_path) > 1000:  # Real image
                                duration = img.get('duration', 5)  # Default 5 seconds per scene
                                f.write(f"file '{img_path}'\n")
                                f.write(f"duration {duration}\n")
                    
                    # Compile video with images
                    if os.path.exists(filelist_path) and os.path.getsize(filelist_path) > 0:
                        temp_video = 'output/temp_video.mp4'
                        
                        # Create video from images
                        cmd = [
                            'ffmpeg', '-y',  # Overwrite output file
                            '-f', 'concat',  # Concat demuxer
                            '-safe', '0',    # Allow unsafe paths
                            '-i', filelist_path,  # Input file list
                            '-c:v', 'libx264',  # Video codec
                            '-pix_fmt', 'yuv420p',  # Pixel format for compatibility
                            '-r', '30',  # Frame rate
                            temp_video
                        ]
                        
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        
                        if result.returncode == 0 and audio_files:
                            # Add audio to video
                            audio_path = None
                            for audio in audio_files:
                                if os.path.exists(audio['audio_path']) and os.path.getsize(audio['audio_path']) > 1000:
                                    audio_path = audio['audio_path']
                                    break
                            
                            if audio_path:
                                cmd = [
                                    'ffmpeg', '-y',
                                    '-i', temp_video,  # Video input
                                    '-i', audio_path,  # Audio input
                                    '-c:v', 'copy',    # Copy video stream
                                    '-c:a', 'aac',     # Audio codec
                                    '-shortest',       # Match shortest stream
                                    video_path
                                ]
                                
                                result = subprocess.run(cmd, capture_output=True, text=True)
                                
                                if result.returncode == 0:
                                    # Clean up temp file
                                    os.remove(temp_video)
                                    print(f"✅ Vídeo FFmpeg compilado com áudio: {video_path}")
                                else:
                                    print(f"⚠️ Erro ao adicionar áudio: {result.stderr}")
                                    # Use video without audio
                                    os.rename(temp_video, video_path)
                            else:
                                # No valid audio found, use video only
                                os.rename(temp_video, video_path)
                                print(f"✅ Vídeo FFmpeg compilado (sem áudio): {video_path}")
                        else:
                            print(f"⚠️ Erro na compilação FFmpeg: {result.stderr}")
                            # Fallback to mock
                            raise Exception("FFmpeg compilation failed")
                    else:
                        print("⚠️ Nenhuma imagem válida encontrada para FFmpeg")
                        raise Exception("No valid images for FFmpeg")
                
                else:
                    # Fallback to mock
                    raise Exception("FFmpeg not available or no images")
                
                state.update({
                    'video_path': video_path,
                    'video_size': os.path.getsize(video_path) if os.path.exists(video_path) else 0,
                    'generation_method': 'ffmpeg',
                    'current_step': 'video_compiled',
                    'status': 'completed'
                })
                
            except Exception as e:
                print(f"⚠️ FFmpeg falhou: {e}")
                print("💡 Usando mock de vídeo")
                
                # Fallback mock generation
                with open(video_path, 'w') as f:
                    f.write(f"Mock video compiled from {len(scene_images)} images and {len(audio_files)} audio files")
                
                state.update({
                    'video_path': video_path,
                    'video_size': os.path.getsize(video_path),
                    'generation_method': 'mock',
                    'current_step': 'video_compiled',
                    'status': 'completed'
                })
            
            print(f"✅ Vídeo finalizado: {video_path}")
            return state
        
        # Create workflow graph
        workflow = StateGraph(Open3DAgentState)
        
        # Add nodes
        workflow.add_node("extract_story", extract_story)
        workflow.add_node("generate_scenes", generate_scenes)
        workflow.add_node("generate_images", generate_images)
        workflow.add_node("generate_audio", generate_audio)
        workflow.add_node("compile_video", compile_video)
        
        # Set entry point
        workflow.set_entry_point("extract_story")
        
        # Add edges
        workflow.add_edge("extract_story", "generate_scenes")
        workflow.add_edge("generate_scenes", "generate_images")
        workflow.add_edge("generate_images", "generate_audio")
        workflow.add_edge("generate_audio", "compile_video")
        workflow.add_edge("compile_video", END)
        
        # Compile workflow
        compiled_workflow = workflow.compile()
        
        print("✅ Workflow LangGraph criado com sucesso!")
        return compiled_workflow
        
    except ImportError as e:
        print(f"❌ Erro ao importar dependências LangGraph: {e}")
        print("💡 Certifique-se de que langgraph está instalado")
        return None
    except Exception as e:
        print(f"❌ Erro ao criar workflow: {e}")
        return None



@dataclass
class WorkflowConfig:
    """Configuration for Open3D workflow"""
    max_iterations: int = 10
    enable_visualization: bool = True
    output_format: str = "mp4"
