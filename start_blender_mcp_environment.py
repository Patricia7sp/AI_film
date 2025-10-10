#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para iniciar todo o ambiente LangGraph+Blender MCP em um único comando.
Este script:
1. Inicia o Blender com o addon MCP ativo
2. Inicia o servidor MCP principal
3. Verifica se todas as conexões estão funcionando
"""

import os
import sys
import time
import signal
import argparse
import subprocess
import threading
import logging
import shutil
from pathlib import Path

# Configurar logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("blender_mcp_environment")

# Obter diretório base
BASE_DIR = Path(__file__).parent.absolute()
SCRIPT_DIR = BASE_DIR / "script"
SETTING_DIR = BASE_DIR / "setting"

# Variáveis globais para processos
blender_process = None
mcp_server_process = None

def load_env_variables():
    """Carrega variáveis do arquivo .env"""
    env_vars = {}
    env_file = SETTING_DIR / ".env"
    
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    
    return env_vars

def start_blender():
    """Inicia o Blender com o addon MCP"""
    global blender_process
    
    # Caminhos para executáveis do Blender em diferentes sistemas
    blender_paths = {
        "darwin": "/Applications/Blender.app/Contents/MacOS/Blender",
        "win32": r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
        "linux": "/usr/bin/blender"
    }
    
    blender_path = blender_paths.get(sys.platform)
    if not blender_path or not os.path.exists(blender_path):
        logger.error(f"Blender não encontrado em {blender_path}")
        return False
    
    # Script para iniciar o addon MCP
    addon_script = SCRIPT_DIR / "start_blender_addon_server.py"
    
    # Iniciar Blender
    try:
        logger.info("Iniciando Blender com o addon MCP...")
        blender_process = subprocess.Popen(
            [blender_path, "--python", str(addon_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Função para monitorar a saída do Blender
        def monitor_blender_output():
            for line in blender_process.stdout:
                logger.info(f"Blender: {line.strip()}")
                if "BlenderMCP server started" in line:
                    logger.info("Addon MCP iniciado com sucesso no Blender")
        
        # Iniciar thread para monitorar saída
        threading.Thread(target=monitor_blender_output, daemon=True).start()
        
        # Aguardar o servidor iniciar
        time.sleep(5)
        
        # Verificar se o processo ainda está em execução
        if blender_process.poll() is not None:
            logger.error("Blender foi encerrado prematuramente")
            return False
        
        logger.info("Blender iniciado com sucesso")
        return True
    
    except Exception as e:
        logger.error(f"Erro ao iniciar Blender: {str(e)}")
        return False

def start_mcp_server(env_vars):
    """Inicia o servidor MCP principal"""
    global mcp_server_process
    
    # Obter configurações do ambiente ou usar valores padrão
    host = env_vars.get("BLENDER_MCP_HOST", "localhost")
    port = env_vars.get("BLENDER_MCP_PORT", "5678")
    addon_port = env_vars.get("BLENDER_ADDON_PORT", "9876")
    
    # Ativar ambiente virtual MCP
    venv_python = BASE_DIR / ".venv_mcp" / "bin" / "python"
    if sys.platform == "win32":
        venv_python = BASE_DIR / ".venv_mcp" / "Scripts" / "python.exe"
    
    if not venv_python.exists():
        logger.error(f"Ambiente virtual MCP não encontrado em {venv_python}")
        logger.info("Execute setup_blender_mcp_env.py para criar o ambiente virtual")
        return False
    
    # Script do servidor MCP
    server_script = SCRIPT_DIR / "blender_mcp_server.py"
    
    # Iniciar servidor MCP
    try:
        logger.info(f"Iniciando servidor MCP em {host}:{port}, conectando ao Blender na porta {addon_port}...")
        mcp_server_process = subprocess.Popen(
            [str(venv_python), str(server_script), "--blender-port", addon_port],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Função para monitorar a saída do servidor MCP
        def monitor_mcp_output():
            for line in mcp_server_process.stdout:
                logger.info(f"MCP: {line.strip()}")
                if "Successfully connected to Blender" in line:
                    logger.info("Servidor MCP conectado com sucesso ao Blender")
        
        # Iniciar thread para monitorar saída
        threading.Thread(target=monitor_mcp_output, daemon=True).start()
        
        # Aguardar o servidor iniciar
        time.sleep(3)
        
        # Verificar se o processo ainda está em execução
        if mcp_server_process.poll() is not None:
            logger.error("Servidor MCP foi encerrado prematuramente")
            return False
        
        logger.info("Servidor MCP iniciado com sucesso")
        return True
    
    except Exception as e:
        logger.error(f"Erro ao iniciar servidor MCP: {str(e)}")
        return False

def cleanup():
    """Encerra todos os processos e limpa recursos"""
    global blender_process, mcp_server_process
    
    logger.info("Encerrando processos...")
    
    if mcp_server_process:
        try:
            mcp_server_process.terminate()
            mcp_server_process.wait(timeout=5)
            logger.info("Servidor MCP encerrado")
        except:
            logger.warning("Não foi possível encerrar o servidor MCP corretamente")
    
    if blender_process:
        try:
            blender_process.terminate()
            blender_process.wait(timeout=5)
            logger.info("Blender encerrado")
        except:
            logger.warning("Não foi possível encerrar o Blender corretamente")

def signal_handler(sig, frame):
    """Manipulador de sinal para encerrar os processos ao interromper o script"""
    logger.info("Interrupção recebida. Encerrando processos...")
    cleanup()
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="Iniciar ambiente LangGraph+Blender MCP")
    parser.add_argument("--mcp-only", action="store_true", help="Iniciar apenas o servidor MCP (assumindo que o Blender já está em execução)")
    parser.add_argument("--blender-only", action="store_true", help="Iniciar apenas o Blender com o addon MCP")
    args = parser.parse_args()
    
    # Registrar manipulador de sinal e função de limpeza
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Carregar variáveis de ambiente
    env_vars = load_env_variables()
    
    # Iniciar Blender se necessário
    if not args.mcp_only:
        if not start_blender():
            logger.error("Falha ao iniciar o Blender")
            cleanup()
            return 1
    
    # Iniciar servidor MCP se necessário
    if not args.blender_only:
        # Verificar/Configurar ambiente virtual MCP
        venv_dir = BASE_DIR / ".venv_mcp"
        setup_script = SCRIPT_DIR / "setup_blender_mcp_env.py"
        if not venv_dir.exists():
            # Verificar se CLI uv está disponível globalmente
            if not shutil.which("uv"):
                logger.error("CLI uv não encontrado. Instale com: pip install uv")
                cleanup()
                return 1
            logger.info("Ambiente MCP não encontrado. Executando setup para criar venv...")
            # Executar setup com cwd no script dir
            ret = subprocess.call([sys.executable, str(setup_script)], cwd=str(SCRIPT_DIR))
            if ret != 0:
                logger.error("Falha ao configurar ambiente virtual MCP")
                cleanup()
                return 1
        if not start_mcp_server(env_vars):
            logger.error("Falha ao iniciar o servidor MCP")
            cleanup()
            return 1
    
    logger.info("""
==============================================
Ambiente LangGraph+Blender MCP iniciado!
==============================================

Para executar o pipeline LangGraph, use:
python script/run_langgraph_story.py

Pressione Ctrl+C para encerrar o ambiente.
==============================================
""")
    
    try:
        # Manter o script em execução até que seja interrompido
        while True:
            time.sleep(1)
            
            # Verificar se os processos ainda estão em execução
            if (not args.mcp_only and blender_process and blender_process.poll() is not None):
                logger.error("Blender foi encerrado")
                break
            
            if (not args.blender_only and mcp_server_process and mcp_server_process.poll() is not None):
                logger.error("Servidor MCP foi encerrado")
                break
    
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário")
    
    finally:
        cleanup()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
