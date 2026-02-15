"""
Pipeline Dagster Aprimorado com Sistema de Logs Estruturados
Integra o StructuredLogger para rastreabilidade completa e logs detalhados.
"""

import os
import time
from datetime import datetime
from typing import Dict, Any, List

from dagster import (
    asset, 
    AssetExecutionContext, 
    Config, 
    RetryPolicy, 
    Backoff,
    get_dagster_logger,
    MaterializeResult,
    MetadataValue
)

import sys
import os

# Add root project path
root_path = '/usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP'
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from open3d_implementation.core.langgraph_adapter import create_open3d_workflow, Open3DAgentState
from open3d_implementation.core.structured_logger import StructuredLogger

class AIFilmPipelineConfig(Config):
    """Configuração para o pipeline de filme AI com logs estruturados"""
    session_id: str = "enhanced_logging_001"
    story_input: str = ""
    story_file_path: str = ""
    input_type: str = "text"
    max_scenes: int = 8
    quality_threshold: float = 0.9
    enable_structured_logging: bool = True
    log_level: str = "INFO"

# Política de retry robusta para operações com serviços externos
external_service_retry = RetryPolicy(
    max_retries=3,
    delay=2,
    backoff=Backoff.EXPONENTIAL,
)

# Política de retry para modelos AI
ai_model_retry = RetryPolicy(
    max_retries=2,
    delay=5,
    backoff=Backoff.LINEAR,
)

@asset(
    description="Asset multimodal melhorado com logs estruturados detalhados",
    retry_policy=external_service_retry,
    compute_kind="multimodal_processing"
)
def enhanced_multimodal_input_asset(
    context: AssetExecutionContext, 
    config: AIFilmPipelineConfig
) -> Dict[str, Any]:
    """
    Processa entrada multimodal com sistema de logs estruturados completo
    """
    start_time = time.time()
    dagster_logger = get_dagster_logger()
    
    # Inicializar logger estruturado
    structured_logger = StructuredLogger(
        session_id=config.session_id,
        output_dir=os.getcwd()
    )
    
    # Log de início do pipeline completo
    structured_logger.log_workflow_stage("PIPELINE COMPLETO - INÍCIO")
    
    try:
        # Determinar fonte da história
        story_text = ""
        input_source = "unknown"
        
        if config.story_file_path and os.path.exists(config.story_file_path):
            # Carregar de arquivo
            try:
                with open(config.story_file_path, 'r', encoding='utf-8') as f:
                    story_text = f.read().strip()
                input_source = "file"
                file_format = os.path.splitext(config.story_file_path)[1].lower()
                
                dagster_logger.info(f"📁 História carregada de arquivo: {config.story_file_path}")
                dagster_logger.info(f"📄 Formato: {file_format}, Tamanho: {len(story_text)} caracteres")
                
            except Exception as e:
                dagster_logger.warning(f"Erro ao ler arquivo {config.story_file_path}: {e}")
                story_text = config.story_input
                input_source = "text_fallback"
        else:
            # Usar texto direto
            story_text = config.story_input
            input_source = "text_direct"
            file_format = "txt"
        
        if not story_text:
            raise ValueError("Nenhuma história fornecida via arquivo ou texto direto")
        
        # Preparar estado inicial com logger estruturado
        initial_state = Open3DAgentState(
            session_id=config.session_id,
            story_text=story_text,
            input_type=config.input_type,
            structured_logger=structured_logger,  # Adicionar logger ao estado
            max_scenes=config.max_scenes,
            metadata={
                "input_source": input_source,
                "story_file_path": config.story_file_path if config.story_file_path else None,
                "file_format": file_format,
                "story_length": len(story_text),
                "timestamp": datetime.now().isoformat(),
                "quality_threshold": config.quality_threshold,
                "structured_logging_enabled": config.enable_structured_logging
            }
        )
        
        execution_time = time.time() - start_time
        
        # Log estruturado de sucesso
        structured_logger.log_workflow_stage("PROCESSAMENTO MULTIMODAL", "completed")
        
        # Metadata rica para Dagster
        context.add_output_metadata({
            "story_length": len(story_text),
            "input_source": input_source,
            "file_format": file_format,
            "execution_time_seconds": execution_time,
            "max_scenes": config.max_scenes,
            "session_id": config.session_id,
            "structured_logging": "enabled" if config.enable_structured_logging else "disabled"
        })
        
        dagster_logger.info(f"✅ Entrada multimodal processada com sucesso em {execution_time:.2f}s")
        
        # Retornar como dicionário para compatibilidade com LangGraph
        return {
            'session_id': initial_state['session_id'],
            'story_text': initial_state['story_text'],
            'input_type': initial_state['input_type'],
            'structured_logger': initial_state.get('structured_logger'),
            'max_scenes': initial_state.get('max_scenes', 8),
            'metadata': initial_state.get('metadata', {}),
            'input_source': input_source,
            'file_format': file_format,
            'story_length': len(story_text)
        }
        
    except Exception as e:
        structured_logger.log_error("multimodal_input", str(e))
        dagster_logger.error(f"❌ Falha no processamento multimodal: {e}")
        raise

@asset(
    description="Workflow LangGraph com logs estruturados integrados",
    retry_policy=ai_model_retry,
    compute_kind="langgraph_workflow"
)
def enhanced_langgraph_workflow_asset(
    context: AssetExecutionContext,
    enhanced_multimodal_input_asset: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Executa workflow LangGraph com sistema de logs estruturados
    """
    start_time = time.time()
    dagster_logger = get_dagster_logger()
    
    # Obter logger estruturado do estado
    structured_logger = enhanced_multimodal_input_asset.get('structured_logger')
    if not structured_logger:
        structured_logger = StructuredLogger(
            session_id=enhanced_multimodal_input_asset.get('session_id', 'default')
        )
    
    try:
        structured_logger.log_workflow_stage("EXECUÇÃO LANGGRAPH")
        
        # Criar workflow
        workflow = create_open3d_workflow()
        
        if workflow is None:
            raise ValueError("Não foi possível criar o workflow LangGraph")
        
        # Preparar estado inicial para o workflow
        initial_state = {
            'story_text': enhanced_multimodal_input_asset.get('story_text', ''),
            'messages': [],
            'current_step': 'initialized',
            'scene_data': {},
            'generated_content': {},
            'enhanced_multimodal_input_asset': enhanced_multimodal_input_asset
        }
        
        # Executar com logs detalhados
        dagster_logger.info("🚀 Iniciando execução do workflow LangGraph...")
        
        final_state = workflow.invoke(initial_state)
        
        # Coletar estatísticas finais
        scenes_count = len(final_state.get('scenes', []))
        images_count = len(final_state.get('scene_images', []))
        audio_count = len(final_state.get('audio_files', []))
        
        execution_time = time.time() - start_time
        
        # Log estruturado de conclusão do pipeline
        if structured_logger:
            total_files = images_count + audio_count
            output_dir = final_state.get('output_dirs', {}).get('base', os.getcwd())
            
            structured_logger.log_pipeline_completion(
                total_scenes=scenes_count,
                total_files=total_files,
                output_directory=output_dir,
                execution_time=execution_time
            )
        
        # Metadata detalhada para Dagster
        context.add_output_metadata({
            "scenes_generated": scenes_count,
            "images_generated": images_count,
            "audio_files_generated": audio_count,
            "total_media_files": images_count + audio_count,
            "execution_time_seconds": execution_time,
            "workflow_status": "completed",
            "quality_scores": MetadataValue.json({
                "average_scene_score": _calculate_average_scene_score(final_state),
                "validation_pass_rate": _calculate_validation_pass_rate(final_state)
            }),
            "output_structure": MetadataValue.json({
                "base_dir": final_state.get('output_dirs', {}).get('base'),
                "images_dir": final_state.get('output_dirs', {}).get('images'),
                "audio_dir": final_state.get('output_dirs', {}).get('audio')
            })
        })
        
        dagster_logger.info(f"🎉 Workflow LangGraph concluído com sucesso!")
        dagster_logger.info(f"📊 Estatísticas: {scenes_count} cenas, {images_count} imagens, {audio_count} áudios")
        dagster_logger.info(f"⏱️ Tempo total: {execution_time:.2f}s")
        
        return final_state
        
    except Exception as e:
        if structured_logger:
            structured_logger.log_error("langgraph_workflow", str(e))
        dagster_logger.error(f"❌ Falha na execução do workflow: {e}")
        raise

@asset(
    description="Validação final com logs estruturados e relatórios detalhados",
    compute_kind="quality_validation",
    deps=[enhanced_langgraph_workflow_asset]
)
def enhanced_validation_asset(
    context: AssetExecutionContext,
    enhanced_langgraph_workflow_asset: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validação final com sistema de logs estruturados e relatórios
    """
    dagster_logger = get_dagster_logger()
    
    # Obter logger estruturado
    structured_logger = enhanced_langgraph_workflow_asset.get('structured_logger')
    
    if structured_logger:
        structured_logger.log_workflow_stage("VALIDAÇÃO FINAL")
    
    try:
        scenes = enhanced_langgraph_workflow_asset.get('scenes', [])
        validation_results = enhanced_langgraph_workflow_asset.get('validation_results', {})
        
        # Calcular métricas detalhadas
        total_scenes = len(scenes)
        approved_scenes = sum(1 for scene in scenes if scene.get('validation', {}).get('approved', False))
        average_score = validation_results.get('average_score', 0)
        
        # Determinar status geral
        quality_status = "HIGH" if average_score >= 85 else "MEDIUM" if average_score >= 70 else "LOW"
        pipeline_success = approved_scenes >= (total_scenes * 0.8) and average_score >= 70
        
        # Coletar caminhos de arquivos para links diretos
        file_paths = []
        
        # Adicionar imagens
        for scene in scenes:
            if scene.get('scene_image'):
                file_paths.append({
                    "type": "image",
                    "scene_id": scene.get('id'),
                    "path": scene.get('scene_image'),
                    "description": f"Imagem da cena {scene.get('id')}"
                })
        
        # Adicionar áudios
        audio_files = enhanced_langgraph_workflow_asset.get('audio_files', [])
        for audio in audio_files:
            file_paths.append({
                "type": "audio",
                "scene_id": audio.get('scene_id'),
                "path": audio.get('main_audio_path'),
                "description": f"Áudio da cena {audio.get('scene_id')}"
            })
        
        # Log estruturado de conclusão
        if structured_logger:
            structured_logger.log_workflow_stage("VALIDAÇÃO FINAL", "completed")
            structured_logger.log_workflow_stage("PIPELINE COMPLETO", "completed")
        
        # Metadata completa para Dagster
        context.add_output_metadata({
            "total_scenes": total_scenes,
            "approved_scenes": approved_scenes,
            "approval_rate_percent": (approved_scenes / total_scenes * 100) if total_scenes > 0 else 0,
            "average_quality_score": average_score,
            "quality_status": quality_status,
            "pipeline_success": pipeline_success,
            "total_files_generated": len(file_paths),
            "file_breakdown": MetadataValue.json({
                "images": len([f for f in file_paths if f["type"] == "image"]),
                "audio": len([f for f in file_paths if f["type"] == "audio"])
            }),
            "quality_distribution": MetadataValue.json({
                "high_quality_scenes": len([s for s in scenes if s.get('validation', {}).get('score', 0) >= 85]),
                "medium_quality_scenes": len([s for s in scenes if 70 <= s.get('validation', {}).get('score', 0) < 85]),
                "low_quality_scenes": len([s for s in scenes if s.get('validation', {}).get('score', 0) < 70])
            })
        })
        
        validation_summary = {
            "pipeline_success": pipeline_success,
            "quality_status": quality_status,
            "metrics": {
                "total_scenes": total_scenes,
                "approved_scenes": approved_scenes,
                "average_score": average_score
            },
            "file_paths": file_paths,
            "structured_logging_enabled": True
        }
        
        dagster_logger.info(f"✅ Validação concluída - Status: {quality_status}")
        dagster_logger.info(f"📊 {approved_scenes}/{total_scenes} cenas aprovadas ({approved_scenes/total_scenes*100:.1f}%)")
        
        return validation_summary
        
    except Exception as e:
        if structured_logger:
            structured_logger.log_error("final_validation", str(e))
        dagster_logger.error(f"❌ Falha na validação final: {e}")
        raise

# Funções auxiliares
def _calculate_average_scene_score(state: Dict[str, Any]) -> float:
    """Calcular score médio das cenas"""
    scenes = state.get('scenes', [])
    if not scenes:
        return 0.0
    
    total_score = sum(scene.get('validation', {}).get('score', 0) for scene in scenes)
    return total_score / len(scenes)

def _calculate_validation_pass_rate(state: Dict[str, Any]) -> float:
    """Calcular taxa de aprovação das cenas"""
    scenes = state.get('scenes', [])
    if not scenes:
        return 0.0
    
    approved = sum(1 for scene in scenes if scene.get('validation', {}).get('approved', False))
    return (approved / len(scenes)) * 100
