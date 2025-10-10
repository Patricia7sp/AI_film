#!/usr/bin/env python3
"""
Módulo de logging compartilhado para LangGraph MCP
Fornece configuração de logging unificada para todos os componentes do sistema
"""

import os
import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
import datetime

# Diretório para logs
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Arquivo de log principal com data
log_filename = f"langgraph_mcp_{datetime.datetime.now().strftime('%Y%m%d')}.log"
log_path = os.path.join(LOG_DIR, log_filename)

# Formatos de log
DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
SIMPLE_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

def setup_logger(name=None, level=logging.INFO, log_to_file=True, log_format=DEFAULT_FORMAT, 
                log_file=None, max_size=10*1024*1024, backup_count=5):
    """
    Configurar um logger com formatos e handlers unificados
    
    Args:
        name: Nome do logger (None para root logger)
        level: Nível de logging (default: INFO)
        log_to_file: Se deve logar para arquivo (default: True)
        log_format: Formato do log (default: DEFAULT_FORMAT)
        log_file: Caminho para arquivo de log específico (default: None, usa o principal)
        max_size: Tamanho máximo do arquivo de log antes de rotação
        backup_count: Número de backups a manter
        
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remover handlers existentes para evitar duplicação
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Criar formatter
    formatter = logging.Formatter(log_format)
    
    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler para arquivo se solicitado
    if log_to_file:
        file_path = log_file if log_file else log_path
        file_handler = RotatingFileHandler(
            file_path, 
            maxBytes=max_size, 
            backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# Configurações pré-definidas para diferentes componentes
def get_app_logger():
    """Logger para o servidor Flask principal (app.py)"""
    return setup_logger("app", log_format=SIMPLE_FORMAT)

def get_open3d_logger():
    """Logger para o servidor Open3D MCP"""
    return setup_logger("open3d_mcp", log_format=DEFAULT_FORMAT)

def get_blender_logger():
    """Logger para o servidor Blender MCP"""
    return setup_logger("blender_mcp", log_format=DEFAULT_FORMAT)

def get_comfyui_logger():
    """Logger para integrações com ComfyUI"""
    return setup_logger("comfyui", log_format=DEFAULT_FORMAT)

def get_langgraph_logger():
    """Logger para o fluxo LangGraph"""
    return setup_logger("langgraph", log_format=DEFAULT_FORMAT)

# Logger padrão para uso geral
default_logger = setup_logger("langgraph_mcp", log_format=SIMPLE_FORMAT)
