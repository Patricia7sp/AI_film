"""
Ponto de entrada principal para a aplicação FastAPI.
Gerencia a inicialização e o gerenciamento de todos os serviços.
"""

from contextlib import asynccontextmanager
import json
import signal
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


class BlenderConfig(TypedDict):
    executable: str


class ServerConfig(TypedDict):
    host: str
    port: int


class ComfyUIConfig(TypedDict):
    port: int


class SecurityConfig(TypedDict):
    cors_allowed_origins: list[str]


class AppConfig(TypedDict):
    blender: BlenderConfig
    server: ServerConfig
    comfyui: ComfyUIConfig
    security: SecurityConfig


DEFAULT_CONFIG: AppConfig = {
    "blender": {"executable": "blender"},
    "server": {"host": "0.0.0.0", "port": 8000},
    "comfyui": {"port": 8188},
    "security": {"cors_allowed_origins": ["http://localhost:3000"]},
}

# Configurações
BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config" / "mcp_config.json"


# Carregar configurações
def load_config() -> AppConfig:
    """Carrega as configurações do arquivo de configuração."""
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG

    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


config = load_config()


# Estado global
class State:
    def __init__(self) -> None:
        self.blender_process = None
        self.comfyui_process = None
        self.is_shutting_down = False


state = State()


# Funções auxiliares
def start_blender_server():
    """Inicia o servidor MCP do Blender."""
    if state.blender_process is not None:
        return

    try:
        blender_path = config["blender"]["executable"]
        script_path = BASE_DIR / "script" / "blender_mcp_addon" / "server.py"
        port = config["server"]["port"]

        cmd = [
            blender_path,
            "--background",
            "--factory-startup",
            "--python",
            str(script_path),
            "--",
            "--port",
            str(port),
        ]

        state.blender_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        # Verificar se o processo foi iniciado com sucesso
        if state.blender_process.poll() is not None:
            raise RuntimeError("Falha ao iniciar o servidor Blender MCP")

        return state.blender_process

    except (KeyError, OSError, RuntimeError) as exc:
        if state.blender_process:
            state.blender_process.terminate()
            state.blender_process = None
        raise RuntimeError(f"Erro ao iniciar o servidor Blender: {exc}") from exc


def start_comfyui():
    """Inicia o servidor ComfyUI."""
    if state.comfyui_process is not None:
        return

    try:
        comfyui_dir = BASE_DIR / "ComfyUI"
        if not (comfyui_dir / "main.py").exists():
            raise FileNotFoundError("Diretório do ComfyUI não encontrado")

        cmd = [
            sys.executable,
            "main.py",
            "--listen",
            "0.0.0.0",
            "--port",
            str(config["comfyui"]["port"]),
        ]

        state.comfyui_process = subprocess.Popen(
            cmd,
            cwd=str(comfyui_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        # Verificar se o processo foi iniciado com sucesso
        if state.comfyui_process.poll() is not None:
            raise RuntimeError("Falha ao iniciar o ComfyUI")

        return state.comfyui_process

    except (FileNotFoundError, KeyError, OSError, RuntimeError) as exc:
        if state.comfyui_process:
            state.comfyui_process.terminate()
            state.comfyui_process = None
        raise RuntimeError(f"Erro ao iniciar o ComfyUI: {exc}") from exc


def stop_services():
    """Para todos os serviços em execução."""
    if state.is_shutting_down:
        return

    state.is_shutting_down = True

    if state.blender_process:
        try:
            state.blender_process.terminate()
            state.blender_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            state.blender_process.kill()
        finally:
            state.blender_process = None

    if state.comfyui_process:
        try:
            state.comfyui_process.terminate()
            state.comfyui_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            state.comfyui_process.kill()
        finally:
            state.comfyui_process = None


# Configuração do FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerenciador de ciclo de vida da aplicação."""
    # Iniciar serviços
    try:
        print("Iniciando serviços...")
        start_blender_server()
        start_comfyui()
        print("Serviços iniciados com sucesso!")

        yield

    except (FileNotFoundError, KeyError, OSError, RuntimeError) as exc:
        print(f"Erro ao iniciar serviços: {exc}", file=sys.stderr)
        stop_services()
        sys.exit(1)

    finally:
        print("Parando serviços...")
        stop_services()
        print("Serviços parados com sucesso!")


# Criar aplicação FastAPI
app = FastAPI(
    title="LangGraph MCP Server",
    description="API para integração com Blender e ComfyUI",
    version="1.0.0",
    lifespan=lifespan,
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config["security"]["cors_allowed_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rotas da API
@app.get("/")
async def read_root():
    """Rota raiz da API."""
    return {
        "name": "LangGraph MCP Server",
        "version": "1.0.0",
        "status": "running",
        "services": {
            "blender_mcp": {
                "status": (
                    "running"
                    if state.blender_process and state.blender_process.poll() is None
                    else "stopped"
                ),
                "port": config["server"]["port"],
            },
            "comfyui": {
                "status": (
                    "running"
                    if state.comfyui_process and state.comfyui_process.poll() is None
                    else "stopped"
                ),
                "port": config["comfyui"]["port"],
            },
        },
    }


@app.get("/health")
async def health_check():
    """Verifica a saúde da aplicação."""
    return {"status": "healthy"}


# Manipuladores de sinal para desligamento gracioso
def handle_shutdown(signum, frame):
    """Manipula sinais de desligamento."""
    print("\nRecebido sinal de desligamento, encerrando graciosamente...")
    stop_services()
    sys.exit(0)


# Registrar manipuladores de sinal
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

if __name__ == "__main__":
    # Iniciar o servidor Uvicorn
    uvicorn.run(
        "app.main:app",
        host=config["server"]["host"],
        port=config["server"]["port"],
        reload=True,
        workers=1,
        log_level="info",
    )
