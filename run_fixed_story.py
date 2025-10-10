#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangGraph MCP Executor com História do Arquivo
=============================================

Este script executa o pipeline de geração de vídeo com uma história
lida diretamente do arquivo no diretório data/historia.txt.

Uso:
    python run_fixed_story.py

Para personalizar a história, edite o arquivo:
    script/data/historia.txt
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# =====================================================================
# CONFIGURAÇÃO DA HISTÓRIA - LENDO DO ARQUIVO historia.txt
# =====================================================================

# Caminho para o arquivo de história
STORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                         "script", "data", "historia.txt")

# Verificar se o arquivo existe
if not os.path.exists(STORY_FILE):
    logger.error(f"Arquivo de história não encontrado: {STORY_FILE}")
    sys.exit(1)

# Ler o conteúdo do arquivo
try:
    with open(STORY_FILE, 'r', encoding='utf-8') as f:
        STORY_TEXT = f.read()
    logger.info(f"História carregada com sucesso do arquivo: {STORY_FILE}")
    logger.info(f"Tamanho da história: {len(STORY_TEXT)} caracteres")
except Exception as e:
    logger.error(f"Erro ao ler o arquivo de história: {e}")
    sys.exit(1)

# Diretório de saída para os vídeos gerados
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# =====================================================================
# NÃO EDITE ABAIXO DESTA LINHA (a menos que você saiba o que está fazendo)
# =====================================================================

def main():
    """Função principal que executa o script run_langgraph_story.py com a história predefinida."""
    
    logger.info("Iniciando execução com história fixa")
    logger.info(f"Texto da história: \n{STORY_TEXT}")
    
    # Criar diretório de saída se não existir
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger.info(f"Diretório de saída: {OUTPUT_DIR}")
    
    # Caminho para o script principal
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                              "script", "run_langgraph_story.py")
    
    # Verificar se o script existe
    if not os.path.exists(script_path):
        logger.error(f"Script não encontrado: {script_path}")
        return 1
    
    # Argumentos para o script
    args = [
        sys.executable,
        script_path,
        "--story", STORY_TEXT,
        "--output-dir", OUTPUT_DIR,
        "--resolution", "1280x720",  # Resolução menor para processamento mais rápido
        "--fps", "30",
        "--duration", "60",  # Duração em segundos
    ]
    
    logger.info("Executando pipeline de geração de vídeo...")
    
    try:
        # Executar o script com os argumentos
        process = subprocess.run(
            args,
            check=True,
            text=True,
            stderr=subprocess.STDOUT
        )
        
        logger.info("Pipeline concluído com sucesso!")
        return 0
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Erro ao executar o pipeline: {e}")
        logger.error(f"Saída: {e.output}")
        return 1
    
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
