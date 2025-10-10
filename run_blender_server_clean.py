#!/usr/bin/env python
"""
Script standalone para iniciar um servidor HTTP simples no Blender 
que funciona como um servidor MCP básico na porta 9876.

Este script inicia o Blender em modo background e executa um servidor HTTP
que pode ser usado para importar cenas 3D a partir de arquivos JSON.
"""
from __future__ import print_function
import os
import sys
import time
import socket
import subprocess
import threading
import tempfile
import logging
import json
import shutil
import traceback
import platform
import signal
import atexit
import tempfile
import shutil
from datetime import datetime
import http.client

# Configuração de modo de depuração
DEBUG_MODE = False  # Definir como True para manter arquivos temporários

# Configuração de logging avançada
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = logging.DEBUG
LOG_FILE = '/tmp/blender_server.log'

# Configurar logging para arquivo e console
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Criar logger
logger = logging.getLogger('blender_runner')

# Adicionar informações iniciais ao log
logger.info("=" * 80)
logger.info(f"Iniciando Blender Server - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
logger.info(f"Python: {sys.version}")
logger.info(f"Sistema Operacional: {platform.system()} {platform.release()} {platform.version()}")
logger.info(f"Diretório de trabalho: {os.getcwd()}")
logger.info(f"Diretório do script: {os.path.dirname(os.path.abspath(__file__))}")
logger.info("=" * 80)

# ===========================================================================
# Configurações globais
# ===========================================================================

# Porta do servidor
PORT = 9876

# Caminho para este script
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Nome do arquivo temporário para o script do servidor
TEMP_SERVER_FILE = os.path.join(CURRENT_DIR, "temp_blender_server.py")

# Variáveis globais para controle do processo
process = None
server_active = False

# ===========================================================================
# Funções de utilidade
# ===========================================================================

def setup_signal_handlers():
    """Configura manipuladores de sinal para encerramento gracioso."""
    def signal_handler(sig, frame):
        logger.info(f"Recebido sinal {sig}, encerrando...")
        cleanup()
        sys.exit(0)
    
    # Registrar manipuladores para os sinais comuns de término
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Ignorar SIGPIPE (pode ocorrer quando o pipe é quebrado)
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except AttributeError:
        # SIGPIPE não está disponível no Windows
        pass

def cleanup():
    """Limpar recursos e encerrar processos filhos."""
    global process, server_active
    
    logger.info("Limpando recursos...")
    
    # Encerrar o processo do Blender se estiver rodando
    if process and process.poll() is None:
        logger.info("Encerrando processo do Blender...")
        try:
            # Tentar encerrar graciosamente primeiro
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Processo não respondeu a sinal de término, forçando encerramento...")
            process.kill()
            process.wait()
        except Exception as e:
            logger.error(f"Erro ao encerrar processo do Blender: {e}")
    
    # Remover arquivo temporário
    try:
        if os.path.exists(TEMP_SERVER_FILE):
            os.remove(TEMP_SERVER_FILE)
            logger.info(f"Arquivo temporário removido: {TEMP_SERVER_FILE}")
    except Exception as e:
        logger.error(f"Erro ao remover arquivo temporário: {e}")
    
    server_active = False
    logger.info("Limpeza concluída")

def find_blender():
    """Encontrar o executável do Blender."""
    logger.info("Procurando Blender...")
    
    # Primeiro tentar usar BLENDER_PATH se definido
    blender_path = os.environ.get('BLENDER_PATH')
    if blender_path:
        logger.info(f"BLENDER_PATH definido como: {blender_path}")
        try:
            # Testar se o caminho é válido
            if os.path.isfile(blender_path) and os.access(blender_path, os.X_OK):
                logger.info(f"Caminho {blender_path} é um arquivo executável válido")
                return blender_path
            else:
                logger.error(f"O caminho {blender_path} não é um arquivo executável válido")
        except Exception as e:
            logger.error(f"Erro ao verificar {blender_path}: {str(e)}")
    
    # Se não encontrou via BLENDER_PATH, tentar caminhos padrão
    logger.info("BLENDER_PATH não definido ou inválido, tentando caminhos padrão...")
    potential_paths = [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/usr/bin/blender",
        "/usr/local/bin/blender",
        "/usr/local/blender/blender"
    ]
    
    for path in potential_paths:
        try:
            logger.info(f"Testando caminho: {path}")
            # Testar se o comando existe e é executável
            if os.path.isfile(path) and os.access(path, os.X_OK):
                logger.info(f"Caminho {path} é um arquivo executável válido")
                return path
            
            # Também testar execução direta
            subprocess.run([path, "--version"], 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE, 
                          check=True,
                          timeout=5)
            logger.info(f"Caminho {path} funciona via execução")
            return path
            
        except (subprocess.SubprocessError, FileNotFoundError, PermissionError) as e:
            logger.error(f"Erro ao testar {path}: {str(e)}")
            continue
    
    logger.error("Não foi possível encontrar o Blender em nenhum dos caminhos")
    return None

def main():
    """Função principal para iniciar o servidor Blender MCP."""
    global process, server_active
    
    # Ativar servidor
    server_active = True
    
    # Verificar o Blender
    blender_path = find_blender()
    if not blender_path:
        logger.error("Blender não encontrado.")
        return 1
    
    logger.info(f"Blender encontrado: {blender_path}")
    
    # Criar script do servidor que será executado no Blender
    blender_server_script = '''#!/usr/bin/env python
import bpy
import sys
import os
import time
import socket
import threading
import json
import traceback
import datetime

# Configurações
PORT = 9876
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

print("=== Iniciando Servidor Blender MCP Simples na porta 9876 ===")
print(f"Blender versão: {bpy.app.version_string}")
print(f"Python versão: {sys.version}")
print(f"Diretório do script: {SCRIPT_DIR}")
sys.stdout.flush()

# Função para log
def log(message):
    print(message)
    sys.stdout.flush()
    with open("/tmp/blender_mcp_server.log", "a") as f:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {message}\\n")

# Função para o servidor TCP
def simple_server():
    log("Iniciando servidor TCP na porta " + str(PORT))
    
    # Criar e configurar o socket
    server = None
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", PORT))
        server.listen(5)
        server.settimeout(1)  # Timeout para verificar interrupções
        
        log(f"Servidor TCP iniciado na porta {PORT}")
        
        # Loop principal do servidor
        while True:
            try:
                # Aceitar conexões
                client, addr = server.accept()
                log(f"Conexão de {addr}")
                
                # Responder ao cliente
                response = f"Blender MCP Server v{bpy.app.version_string}\\n"
                client.send(response.encode("utf-8"))
                client.close()
            except socket.timeout:
                # Timeout normal para verificação periódica
                continue
            except Exception as e:
                log(f"Erro no servidor: {str(e)}")
                break
    except Exception as e:
        log(f"Erro ao iniciar servidor: {str(e)}")
    finally:
        if server:
            server.close()
        log("Servidor encerrado")

# Ponto de entrada principal
if __name__ == "__main__":
    log(f"Iniciando servidor MCP no Blender {bpy.app.version_string}")
    log(f"Diretório do script: {SCRIPT_DIR}")
    
    # Definir uma variável global no Blender para manter o script rodando
    bpy.running_mcp_server = True
    
    # Iniciar servidor em uma thread separada
    server_thread = threading.Thread(target=simple_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Registrar uma função para ser executada a cada segundo pelo timer do Blender
    def keep_alive():
        log("Blender MCP Server ainda ativo")
        return 1.0  # Chamar novamente em 1 segundo
    
    # Registrar o timer no Blender para manter o script rodando
    bpy.app.timers.register(keep_alive, persistent=True)
    
    log("Timer registrado, servidor MCP ativo")
    
    # Loop adicional para garantir que o script não termine
    try:
        while True:
            time.sleep(10)
            if hasattr(bpy, "running_mcp_server") and bpy.running_mcp_server:
                log("Script principal ainda ativo")
            else:
                break
    except KeyboardInterrupt:
        log("Interrupção recebida, encerrando...")
'''
    
    # Escrever o script temporário
    try:
        with open(TEMP_SERVER_FILE, 'w', encoding='utf-8') as f:
            f.write(blender_server_script)
        
        # Garantir permissão de execução
        os.chmod(TEMP_SERVER_FILE, 0o755)
        logger.info(f"Script temporário criado: {TEMP_SERVER_FILE}")
        
    except Exception as e:
        logger.error(f"Erro ao criar script temporário: {str(e)}")
        return 1
    
    # Executar Blender com o script
    try:
        cmd = [blender_path, "--background", "-P", TEMP_SERVER_FILE]
        logger.info(f"Executando comando: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        logger.info(f"Processo do Blender iniciado com PID: {process.pid}")
        
        # Iniciar thread para capturar saída
        def log_output(pipe):
            for line in iter(pipe.readline, ''):
                if line:
                    line = line.strip()
                    logger.info(f"Blender[{process.pid}]: {line}")
        
        output_thread = threading.Thread(
            target=log_output,
            args=(process.stdout,),
            daemon=True
        )
        output_thread.start()
        
        # Aguardar um pouco para verificar se o processo inicia corretamente
        time.sleep(2)
        if process.poll() is not None:
            logger.error(f"Blender encerrou prematuramente com código: {process.poll()}")
            return 1
        
        logger.info(f"Servidor Blender MCP iniciado na porta {PORT}")
        return 0
        
    except Exception as e:
        logger.error(f"Erro ao iniciar o processo do Blender: {str(e)}")
        return 1

# Ponto de entrada principal
if __name__ == "__main__":
    # Registrar manipuladores de sinais para encerramento gracioso
    setup_signal_handlers()
    
    # Executar a função principal
    exit_code = main()
    
    if exit_code == 0:
        # Esta mensagem indica que o script run_blender_server.py iniciou o Blender com sucesso
        logger.info("Processo do Blender foi iniciado. O script run_blender_server.py agora manterá o processo vivo.")
        
        # Loop para manter o processo principal rodando enquanto o Blender estiver ativo
        try:
            start_time = time.time()
            keepalive_count = 0
            
            while process and process.poll() is None:
                # Verificar se o processo está vivo a cada 2 segundos
                time.sleep(2)
                keepalive_count += 1
                
                # Enviar uma mensagem de log a cada 30 segundos para mostrar que está ativo
                if keepalive_count % 15 == 0:
                    uptime = int(time.time() - start_time)
                    logger.info(f"Processo Blender ainda está rodando (PID: {process.pid}, uptime: {uptime}s)")
                    
                    # Testar conexão TCP para verificar se o servidor está respondendo
                    try:
                        # Tentar conectar à porta do servidor
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            s.settimeout(1)
                            result = s.connect_ex(("127.0.0.1", PORT))
                            if result == 0:
                                logger.info(f"Servidor MCP está respondendo na porta {PORT}")
                                # Enviar mensagem de teste
                                s.sendall(b"STATUS")
                                try:
                                    # Tentar ler resposta
                                    data = s.recv(1024)
                                    if data:
                                        logger.info(f"Resposta do servidor: {data[:100].decode('utf-8', errors='ignore')}")
                                except socket.timeout:
                                    logger.warning("Timeout ao esperar resposta do servidor")
                            else:
                                logger.warning(f"Servidor MCP não está respondendo na porta {PORT}")
                    except Exception as e:
                        logger.error(f"Erro ao testar conexão com o servidor: {e}")
        except KeyboardInterrupt:
            logger.info("Interrupção recebida, encerrando o servidor...")
        finally:
            # Limpar recursos ao encerrar
            cleanup()
    else:
        logger.error(f"Falha ao iniciar o processo do Blender. Código de saída: {exit_code}")
    
    logger.info("Execução do script run_blender_server.py finalizada.")
