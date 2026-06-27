#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para verificar e iniciar manualmente os serviços necessários para o LangGraph MCP
"""

import os
import sys
import time
import logging
import argparse
import subprocess
import importlib.util

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('check_services.log')
    ]
)
logger = logging.getLogger("check_services")

def check_spacy_models():
    """
    Verifica se os modelos spaCy necessários estão instalados.
    """
    logger.info("Verificando modelos spaCy...")
    
    # Verificar se o spaCy está instalado
    if importlib.util.find_spec("spacy") is None:
        logger.warning("spaCy não está instalado")
        return False
    
    import spacy
    
    required_models = {
        "pt_core_news_md": "Português (médio)",
        "en_core_web_md": "Inglês (médio)",
        "en_core_web_sm": "Inglês (pequeno)"
    }
    
    all_models_available = True
    
    for model_name, description in required_models.items():
        try:
            # Tentar carregar o modelo para verificar se está instalado
            spacy.load(model_name)
            logger.info(f"✓ Modelo {model_name} ({description}) está instalado")
        except Exception as e:
            logger.warning(f"✗ Modelo {model_name} não está instalado: {str(e)}")
            all_models_available = False
    
    return all_models_available

def check_comfyui():
    """
    Verifica se o ComfyUI está rodando.
    """
    from open3d_implementation.core.comfyui_integration import ComfyUIIntegration
    logger.info("Verificando serviço ComfyUI...")
    
    # base_url agora é resolvido automaticamente (ENV -> config -> default)
    comfyui = ComfyUIIntegration(session_id="check_services")
    logger.info(f"ComfyUI URL resolvida: {comfyui.base_url}")

    is_running = comfyui.check_connection(retry=True, max_retries=3, retry_delay=3, start_if_unavailable=False)

    if is_running:
        logger.info(f"✓ ComfyUI está online em {comfyui.base_url}")
    else:
        logger.warning(f"✗ ComfyUI não está acessível em {comfyui.base_url}")
    
    return is_running

def start_comfyui():
    """
    Tenta iniciar o ComfyUI.
    """
    from open3d_implementation.core.comfyui_integration import ComfyUIIntegration
    logger.info("Tentando iniciar o ComfyUI...")
    
    # Não há API direta para iniciar via integração; orientar usuário e re-testar
    comfyui = ComfyUIIntegration(session_id="check_services")
    logger.info("Não há método start_comfyui_service; inicie o túnel/serviço manualmente (Colab/Cloudflare)")
    logger.info("Após iniciar, a verificação será refeita automaticamente.")

    # Aguardar breve período e re-testar
    time.sleep(5)
    return comfyui.check_connection(retry=True, max_retries=3, retry_delay=3, start_if_unavailable=False)

def check_blender_mcp():
    """
    Verifica se o Blender MCP está rodando.
    """
    from open3d_implementation.core.blender_integration import is_blender_mcp_running
    
    host = os.getenv("BLENDER_MCP_HOST", "localhost")
    port = os.getenv("BLENDER_MCP_PORT", "8080")
    
    logger.info(f"Verificando Blender MCP em {host}:{port}...")
    
    is_running = is_blender_mcp_running(host, port)
    
    if is_running:
        logger.info(f"✓ Blender MCP está rodando em {host}:{port}")
    else:
        logger.warning(f"✗ Blender MCP não está rodando em {host}:{port}")
    
    return is_running

def start_blender_mcp():
    """
    Tenta iniciar o Blender MCP.
    """
    from open3d_implementation.core.blender_integration import BlenderIntegration
    
    logger.info("Tentando iniciar Blender MCP...")
    
    blender = BlenderIntegration()
    
    success = blender.check_mcp_connection(retry=True, start_if_unavailable=True)
    
    if success:
        logger.info("✓ Blender MCP iniciado com sucesso")
    else:
        logger.error("✗ Falha ao iniciar Blender MCP")
    
    return success

def check_gpu():
    """
    Verifica a disponibilidade de GPU.
    """
    logger.info("Verificando disponibilidade de GPU...")
    
    try:
        # Tentar detectar CUDA
        result = subprocess.run(["nvidia-smi"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        if result.returncode == 0:
            gpu_info = result.stdout.decode('utf-8')
            logger.info(f"✓ GPU NVIDIA detectada:\n{gpu_info.strip()}")
            return True, "NVIDIA"
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.info("nvidia-smi não disponível, verificando outras opções de GPU")
        try:
            # Tentar detectar ROCm (AMD)
            result = subprocess.run(["rocm-smi"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            if result.returncode == 0:
                gpu_info = result.stdout.decode('utf-8')
                logger.info(f"✓ GPU AMD detectada:\n{gpu_info.strip()}")
                return True, "AMD"
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
    
    logger.warning("✗ Nenhuma GPU detectada, usando CPU apenas")
    return False, "CPU"

def main():
    """
    Função principal que verifica todos os serviços.
    """
    parser = argparse.ArgumentParser(description='Verificador de serviços LangGraph MCP')
    parser.add_argument('--start', action='store_true', help='Iniciar serviços que não estiverem rodando')
    parser.add_argument('--comfyui-only', action='store_true', help='Verificar apenas o ComfyUI')
    parser.add_argument('--blender-only', action='store_true', help='Verificar apenas o Blender MCP')
    parser.add_argument('--spacy-only', action='store_true', help='Verificar apenas os modelos spaCy')
    
    args = parser.parse_args()
    
    # Verificar se estamos no diretório correto
    if not os.path.exists("open3d_implementation"):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        if not os.path.exists("open3d_implementation"):
            logger.error("Este script deve ser executado a partir do diretório raiz do projeto")
            return 1
    
    # Adicionar o diretório atual ao PYTHONPATH para importações relativas
    sys.path.append(os.getcwd())
    
    logger.info("=== Verificação de Serviços LangGraph MCP ===")
    
    # Verificar GPU
    has_gpu, gpu_type = check_gpu()
    
    # Verificar variáveis de ambiente
    logger.info("\n=== Variáveis de Ambiente ===")
    logger.info(f"BLENDER_PATH: {os.getenv('BLENDER_PATH', 'Não definido')}")
    logger.info(f"COMFYUI_PATH: {os.getenv('COMFYUI_PATH', 'Não definido')}")
    logger.info(f"BLENDER_MCP_HOST: {os.getenv('BLENDER_MCP_HOST', 'localhost (padrão)')}")
    logger.info(f"BLENDER_MCP_PORT: {os.getenv('BLENDER_MCP_PORT', '8080 (padrão)')}")
    logger.info(f"COMFYUI_HOST: {os.getenv('COMFYUI_HOST', 'localhost (padrão)')}")
    logger.info(f"COMFYUI_PORT: {os.getenv('COMFYUI_PORT', '8188 (padrão)')}")
    
    status = {
        "spacy": False,
        "comfyui": False,
        "blender_mcp": False
    }
    
    # Verificar modelos spaCy
    if not args.comfyui_only and not args.blender_only:
        status["spacy"] = check_spacy_models()
    
    # Verificar ComfyUI
    if not args.blender_only and not args.spacy_only:
        status["comfyui"] = check_comfyui()
        if not status["comfyui"] and args.start:
            start_comfyui()
            # Verificar novamente após iniciar
            time.sleep(10)
            status["comfyui"] = check_comfyui()
    
    # Verificar Blender MCP
    if not args.comfyui_only and not args.spacy_only:
        status["blender_mcp"] = check_blender_mcp()
        if not status["blender_mcp"] and args.start:
            start_blender_mcp()
            # Verificar novamente após iniciar
            time.sleep(10)
            status["blender_mcp"] = check_blender_mcp()
    
    # Resumo
    logger.info("\n=== Resumo ===")
    if not args.comfyui_only and not args.blender_only:
        logger.info(f"SpaCy Models: {'✓ Disponível' if status['spacy'] else '✗ Indisponível'}")
    if not args.blender_only and not args.spacy_only:
        logger.info(f"ComfyUI: {'✓ Disponível' if status['comfyui'] else '✗ Indisponível'}")
    if not args.comfyui_only and not args.spacy_only:
        logger.info(f"Blender MCP: {'✓ Disponível' if status['blender_mcp'] else '✗ Indisponível'}")
    logger.info(f"GPU: {'✓ ' + gpu_type if has_gpu else '✗ Não disponível (usando CPU)'}")
    
    # Exibir instruções
    logger.info("\n=== Instruções ===")
    if not args.start:
        logger.info("Para iniciar serviços, execute: python check_services.py --start")
    
    if not all(status.values()):
        logger.warning("Alguns serviços não estão disponíveis. O LangGraph MCP pode usar fallbacks, mas algumas funcionalidades podem estar limitadas.")
        return 1
    
    logger.info("Todos os serviços verificados estão disponíveis!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
