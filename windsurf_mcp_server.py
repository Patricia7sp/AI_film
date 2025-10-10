#!/usr/bin/env python3
"""
Windsurf MCP Server
Um servidor MCP simples para integração com o Claude Desktop
"""

import json
import sys
import logging
from typing import Dict, Any, List

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/windsurf_mcp.log'),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

class WindsurfMCPServer:
    def __init__(self):
        self.tools = {
            "test_connection": {
                "description": "Testa a conexão com o servidor MCP",
                "parameters": {}
            },
            "get_server_info": {
                "description": "Retorna informações sobre o servidor",
                "parameters": {}
            }
        }
        logger.info("WindsurfMCPServer inicializado")
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Processa uma requisição MCP"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        logger.debug(f"Recebida requisição: {method}")
        
        if method == "initialize":
            return self._handle_initialize(request_id)
        elif method == "tools/list":
            return self._handle_list_tools(request_id)
        elif method == "tools/call":
            return self._handle_tool_call(request_id, params)
        else:
            return self._error_response(request_id, f"Método não suportado: {method}")
    
    def _handle_initialize(self, request_id: Any) -> Dict[str, Any]:
        """Inicializa o servidor"""
        logger.info("Servidor inicializado com sucesso")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "windsurf-mcp",
                    "version": "0.1.0"
                }
            }
        }
    
    def _handle_list_tools(self, request_id: Any) -> Dict[str, Any]:
        """Lista as ferramentas disponíveis"""
        tools_list = []
        for name, info in self.tools.items():
            tools_list.append({
                "name": name,
                "description": info["description"],
                "inputSchema": {
                    "type": "object",
                    "properties": info["parameters"],
                    "required": list(info["parameters"].keys())
                }
            })
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": tools_list
            }
        }
    
    def _handle_tool_call(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Executa uma ferramenta"""
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        if tool_name == "test_connection":
            result = {"status": "connected", "message": "Servidor MCP funcionando corretamente"}
        elif tool_name == "get_server_info":
            result = {
                "name": "windsurf-mcp",
                "version": "0.1.0",
                "status": "running"
            }
        else:
            return self._error_response(request_id, f"Ferramenta não encontrada: {tool_name}")
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }
                ]
            }
        }
    
    def _error_response(self, request_id: Any, message: str) -> Dict[str, Any]:
        """Retorna uma resposta de erro"""
        logger.error(f"Erro: {message}")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": message
            }
        }
    
    def run(self):
        """Executa o servidor"""
        logger.info("Servidor MCP iniciado")
        
        try:
            while True:
                line = sys.stdin.readline()
                if not line:
                    logger.info("Entrada fechada, encerrando servidor")
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                try:
                    request = json.loads(line)
                    response = self.handle_request(request)
                    print(json.dumps(response))
                    sys.stdout.flush()
                except json.JSONDecodeError as e:
                    logger.error(f"Erro ao decodificar JSON: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": "Parse error"
                        }
                    }
                    print(json.dumps(error_response))
                    sys.stdout.flush()
                except Exception as e:
                    logger.error(f"Erro não esperado: {e}", exc_info=True)
                    
        except KeyboardInterrupt:
            logger.info("Servidor interrompido pelo usuário")
        except Exception as e:
            logger.error(f"Erro fatal: {e}", exc_info=True)
        finally:
            logger.info("Servidor encerrado")

if __name__ == "__main__":
    server = WindsurfMCPServer()
    server.run()
