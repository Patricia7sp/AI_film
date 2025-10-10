#!/usr/bin/env python3
"""
Servidor MCP para integração com o Blender.
"""
import os
import sys
import time
import argparse
import subprocess
from pathlib import Path

# Configuração
DEFAULT_PORT = 9877
BLENDER_PATH = os.environ.get('BLENDER_PATH', 'blender')
BLENDER_SCRIPT = str(Path('/app/script/blender_mcp_addon/server.py').resolve())

def start_blender_mcp_server(port=DEFAULT_PORT):
    """Inicia o servidor MCP dentro do Blender."""
    cmd = [
        BLENDER_PATH,
        '--background',
        '--factory-startup',
        '--python', BLENDER_SCRIPT,
        '--',
        '--port', str(port)
    ]
    
    print(f"Iniciando servidor MCP na porta {port}...")
    print(f"Comando: {' '.join(cmd)}")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Capturar saída em tempo real
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(f"[Blender MCP] {output.strip()}")
            
            error = process.stderr.readline()
            if error:
                print(f"[Blender MCP ERROR] {error.strip()}")
        
        return process.poll()
    except Exception as e:
        print(f"Erro ao iniciar o servidor MCP: {e}")
        return 1

def main():
    parser = argparse.ArgumentParser(description='Servidor MCP para o Blender')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                      help=f'Porta para o servidor MCP (padrão: {DEFAULT_PORT})')
    args = parser.parse_args()
    
    sys.exit(start_blender_mcp_server(args.port))

if __name__ == '__main__':
    main()
