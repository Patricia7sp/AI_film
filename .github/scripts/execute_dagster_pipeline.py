#!/usr/bin/env python3
"""
🎬 Dagster Pipeline Executor

Script para executar o pipeline Dagster de geração de conteúdo AI
diretamente via Python (sem precisar do Dagster UI).
"""

import os
import sys
from pathlib import Path

# Adicionar root path
root_path = '/usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP'
if root_path not in sys.path:
    sys.path.insert(0, root_path)

def execute_dagster_pipeline(comfyui_url: str, story_input: str = ""):
    """
    Executa o pipeline Dagster diretamente
    """
    print("=" * 70)
    print("🎬 EXECUTANDO DAGSTER PIPELINE DIRETAMENTE")
    print("=" * 70)
    
    # Configurar variáveis de ambiente
    os.environ['COMFYUI_URL'] = comfyui_url
    
    print(f"📝 ComfyUI URL: {comfyui_url}")
    print(f"📖 Story Input: {story_input or '(vazio - será gerado)'}")
    
    try:
        # Importar o pipeline
        from orchestration.enhanced_dagster_pipeline import (
            enhanced_multimodal_input_asset,
            AIFilmPipelineConfig
        )
        
        print("\n✅ Pipeline Dagster importado com sucesso!")
        print("📦 Assets disponíveis:")
        print("   - enhanced_multimodal_input_asset")
        
        # Criar configuração
        config = AIFilmPipelineConfig(
            session_id=f"github_actions_{os.getenv('GITHUB_RUN_ID', 'local')}",
            story_input=story_input,
            input_type="text" if story_input else "generate",
            max_scenes=8,
            quality_threshold=0.9,
            enable_structured_logging=True,
            log_level="INFO"
        )
        
        print(f"\n⚙️ Configuração:")
        print(f"   Session ID: {config.session_id}")
        print(f"   Input Type: {config.input_type}")
        print(f"   Max Scenes: {config.max_scenes}")
        
        # TODO: Executar asset diretamente
        # Por enquanto, apenas confirma que consegue importar
        print("\n💡 Pipeline pronto para execução!")
        print("⚠️ Execução direta de assets ainda não implementada")
        print("   Use Dagster UI ou dagster-graphql para executar")
        
        return True
        
    except ImportError as e:
        print(f"\n❌ Erro ao importar pipeline: {e}")
        print("💡 Verifique se o arquivo enhanced_dagster_pipeline.py existe")
        return False
    except Exception as e:
        print(f"\n❌ Erro ao executar pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Função principal"""
    comfyui_url = os.getenv('COMFYUI_URL')
    
    if not comfyui_url:
        print("❌ COMFYUI_URL não definida!")
        print("💡 Defina: export COMFYUI_URL='https://your-url.trycloudflare.com'")
        sys.exit(1)
    
    # Story input opcional
    story_input = os.getenv('STORY_INPUT', '')
    
    success = execute_dagster_pipeline(comfyui_url, story_input)
    
    if success:
        print("\n✅ Script executado com sucesso!")
        sys.exit(0)
    else:
        print("\n❌ Script falhou!")
        sys.exit(1)


if __name__ == "__main__":
    main()
