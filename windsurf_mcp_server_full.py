#!/usr/bin/env python3
"""
Windsurf MCP Server - Versão Completa
Servidor MCP com ferramentas para desenvolvimento e automação
"""

import json
import sys
import os
import logging
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

# Configurar logging
log_file = "/tmp/windsurf_mcp.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

class WindsurfMCPServer:
    def __init__(self):
        self.base_path = "/usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP"
        logger.info(f"WindsurfMCPServer inicializado - Base path: {self.base_path}")
        
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Processa uma requisição MCP"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        logger.debug(f"Requisição recebida: {method}")
        
        handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_list_tools,
            "tools/call": self._handle_tool_call,
            "notifications/initialized": self._handle_initialized,
            "shutdown": self._handle_shutdown
        }
        
        handler = handlers.get(method)
        if handler:
            if method in ["initialize", "shutdown"]:
                return handler(request_id)
            else:
                return handler(request_id, params)
        else:
            logger.warning(f"Método não suportado: {method}")
            return self._error_response(request_id, f"Método não suportado: {method}")
    
    def _handle_initialize(self, request_id: Any) -> Dict[str, Any]:
        """Inicializa o servidor"""
        logger.info("Inicializando servidor MCP")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {}
                },
                "serverInfo": {
                    "name": "windsurf-mcp",
                    "version": "1.0.0"
                }
            }
        }
    
    def _handle_initialized(self, request_id: Any, params: Dict[str, Any]) -> None:
        """Manipula notificação de inicialização completa"""
        logger.info("Cliente inicializado com sucesso")
        # Notificações não precisam de resposta
        return None
        
    def _handle_shutdown(self, request_id: Any) -> Dict[str, Any]:
        """Encerra o servidor"""
        logger.info("Encerrando servidor")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {}
        }
    
    def _handle_list_tools(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Lista as ferramentas disponíveis"""
        tools = [
            {
                "name": "execute_command",
                "description": "Executa um comando shell no diretório do projeto",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Comando a ser executado"
                        },
                        "working_dir": {
                            "type": "string",
                            "description": "Diretório de trabalho (opcional)"
                        }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "read_file",
                "description": "Lê o conteúdo de um arquivo",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Caminho do arquivo relativo ao diretório base"
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "write_file",
                "description": "Escreve conteúdo em um arquivo",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Caminho do arquivo relativo ao diretório base"
                        },
                        "content": {
                            "type": "string",
                            "description": "Conteúdo a ser escrito"
                        }
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "list_files",
                "description": "Lista arquivos em um diretório",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Caminho do diretório (opcional, padrão é o diretório base)"
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Padrão de busca (opcional, ex: *.py)"
                        }
                    }
                }
            },
            {
                "name": "search_in_files",
                "description": "Busca texto em arquivos",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Padrão de busca (regex)"
                        },
                        "file_pattern": {
                            "type": "string",
                            "description": "Padrão de arquivos (ex: *.py)"
                        },
                        "path": {
                            "type": "string",
                            "description": "Diretório de busca (opcional)"
                        }
                    },
                    "required": ["pattern"]
                }
            },
            {
                "name": "git_status",
                "description": "Mostra o status do repositório Git",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Caminho do repositório (opcional)"
                        }
                    }
                }
            },
            {
                "name": "create_project_structure",
                "description": "Cria uma estrutura de projeto",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "Nome do projeto"
                        },
                        "project_type": {
                            "type": "string",
                            "enum": ["python", "javascript", "react", "django", "fastapi"],
                            "description": "Tipo de projeto"
                        }
                    },
                    "required": ["project_name", "project_type"]
                }
            }
        ]
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": tools
            }
        }
    
    def _handle_tool_call(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Executa uma ferramenta"""
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        logger.info(f"Executando ferramenta: {tool_name}")
        
        try:
            # Mapeamento de ferramentas
            tool_handlers = {
                "execute_command": self._execute_command,
                "read_file": self._read_file,
                "write_file": self._write_file,
                "list_files": self._list_files,
                "search_in_files": self._search_in_files,
                "git_status": self._git_status,
                "create_project_structure": self._create_project_structure
            }
            
            handler = tool_handlers.get(tool_name)
            if not handler:
                return self._error_response(request_id, f"Ferramenta não encontrada: {tool_name}")
            
            result = handler(**tool_args)
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result
                        }
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao executar ferramenta {tool_name}: {e}", exc_info=True)
            return self._error_response(request_id, str(e))
    
    def _execute_command(self, command: str, working_dir: Optional[str] = None) -> str:
        """Executa um comando shell"""
        cwd = working_dir or self.base_path
        
        # Validação de segurança básica
        dangerous_commands = ['rm -rf', 'dd', 'format', 'del /f']
        if any(danger in command.lower() for danger in dangerous_commands):
            return "Comando potencialmente perigoso bloqueado"
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = f"Comando: {command}\n"
            output += f"Código de saída: {result.returncode}\n"
            
            if result.stdout:
                output += f"\nSaída padrão:\n{result.stdout}"
            if result.stderr:
                output += f"\nSaída de erro:\n{result.stderr}"
                
            return output
            
        except subprocess.TimeoutExpired:
            return "Comando excedeu o tempo limite de 30 segundos"
        except Exception as e:
            return f"Erro ao executar comando: {e}"
    
    def _read_file(self, path: str) -> str:
        """Lê um arquivo"""
        full_path = os.path.join(self.base_path, path) if not os.path.isabs(path) else path
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return f"Conteúdo de {path}:\n\n{content}"
        except FileNotFoundError:
            return f"Arquivo não encontrado: {path}"
        except Exception as e:
            return f"Erro ao ler arquivo: {e}"
    
    def _write_file(self, path: str, content: str) -> str:
        """Escreve em um arquivo"""
        full_path = os.path.join(self.base_path, path) if not os.path.isabs(path) else path
        
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Arquivo escrito com sucesso: {path}"
        except Exception as e:
            return f"Erro ao escrever arquivo: {e}"
    
    def _list_files(self, path: str = "", pattern: str = "*") -> str:
        """Lista arquivos em um diretório"""
        search_path = os.path.join(self.base_path, path) if path else self.base_path
        
        try:
            import glob
            files = []
            
            full_pattern = os.path.join(search_path, "**", pattern)
            for file in glob.glob(full_pattern, recursive=True):
                rel_path = os.path.relpath(file, self.base_path)
                if os.path.isfile(file):
                    size = os.path.getsize(file)
                    files.append(f"📄 {rel_path} ({size} bytes)")
                else:
                    files.append(f"📁 {rel_path}/")
            
            if files:
                return f"Arquivos encontrados ({len(files)}):\n" + "\n".join(sorted(files))
            else:
                return "Nenhum arquivo encontrado"
                
        except Exception as e:
            return f"Erro ao listar arquivos: {e}"
    
    def _search_in_files(self, pattern: str, file_pattern: str = "*", path: str = "") -> str:
        """Busca texto em arquivos"""
        search_path = os.path.join(self.base_path, path) if path else self.base_path
        
        try:
            import glob
            results = []
            regex = re.compile(pattern)
            
            full_pattern = os.path.join(search_path, "**", file_pattern)
            for file_path in glob.glob(full_pattern, recursive=True):
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            for i, line in enumerate(f, 1):
                                if regex.search(line):
                                    rel_path = os.path.relpath(file_path, self.base_path)
                                    results.append(f"{rel_path}:{i}: {line.strip()}")
                    except:
                        pass
            
            if results:
                return f"Resultados encontrados ({len(results)}):\n" + "\n".join(results[:50])
            else:
                return "Nenhum resultado encontrado"
                
        except Exception as e:
            return f"Erro na busca: {e}"
    
    def _git_status(self, path: str = "") -> str:
        """Mostra status do Git"""
        repo_path = os.path.join(self.base_path, path) if path else self.base_path
        
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return "Não é um repositório Git ou erro ao executar git status"
            
            if result.stdout:
                return f"Status do Git:\n{result.stdout}"
            else:
                return "Repositório limpo - nenhuma mudança detectada"
                
        except Exception as e:
            return f"Erro ao verificar status do Git: {e}"
    
    def _create_project_structure(self, project_name: str, project_type: str) -> str:
        """Cria estrutura de projeto"""
        project_path = os.path.join(self.base_path, project_name)
        
        structures = {
            "python": {
                "files": ["__init__.py", "main.py", "requirements.txt", "README.md"],
                "dirs": ["src", "tests", "docs"]
            },
            "javascript": {
                "files": ["index.js", "package.json", "README.md", ".gitignore"],
                "dirs": ["src", "tests", "public"]
            },
            "react": {
                "files": ["package.json", "README.md", ".gitignore"],
                "dirs": ["src", "public", "src/components", "src/styles"]
            },
            "django": {
                "files": ["manage.py", "requirements.txt", "README.md"],
                "dirs": ["apps", "config", "static", "templates"]
            },
            "fastapi": {
                "files": ["main.py", "requirements.txt", "README.md", ".env"],
                "dirs": ["app", "app/api", "app/models", "tests"]
            }
        }
        
        structure = structures.get(project_type)
        if not structure:
            return f"Tipo de projeto não suportado: {project_type}"
        
        try:
            # Criar diretório principal
            os.makedirs(project_path, exist_ok=True)
            
            # Criar subdiretórios
            for dir_name in structure["dirs"]:
                os.makedirs(os.path.join(project_path, dir_name), exist_ok=True)
            
            # Criar arquivos
            for file_name in structure["files"]:
                file_path = os.path.join(project_path, file_name)
                if not os.path.exists(file_path):
                    with open(file_path, 'w') as f:
                        if file_name == "README.md":
                            f.write(f"# {project_name}\n\nProjeto {project_type} criado com Windsurf MCP\n")
                        elif file_name == "package.json" and project_type in ["javascript", "react"]:
                            f.write(json.dumps({
                                "name": project_name,
                                "version": "1.0.0",
                                "description": f"{project_type} project",
                                "main": "index.js" if project_type == "javascript" else "src/index.js",
                                "scripts": {
                                    "start": "node index.js" if project_type == "javascript" else "react-scripts start",
                                    "test": "jest" if project_type == "javascript" else "react-scripts test"
                                }
                            }, indent=2))
                        elif file_name == "requirements.txt":
                            if project_type == "django":
                                f.write("django>=4.0\npython-decouple\n")
                            elif project_type == "fastapi":
                                f.write("fastapi\nuvicorn[standard]\npydantic\n")
                            else:
                                f.write("# Adicione suas dependências aqui\n")
            
            return f"Projeto {project_name} ({project_type}) criado com sucesso em {project_path}"
            
        except Exception as e:
            return f"Erro ao criar projeto: {e}"
    
    def _error_response(self, request_id: Any, message: str) -> Dict[str, Any]:
        """Retorna uma resposta de erro"""
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
        logger.info("Servidor MCP Windsurf iniciado")
        logger.info(f"Log disponível em: {log_file}")
        
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
                    
                    # Só enviar resposta se não for None (notificações não precisam de resposta)
                    if response is not None:
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
