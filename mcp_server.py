# server.py
from mcp.server.fastmcp import FastMCP
import traceback
import subprocess

# Crie o servidor MCP
mcp = FastMCP("CineAI")


# Exemplo de ferramenta (tool)
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

# Ferramenta de debug de código Python
@mcp.tool()
def debug_code(code: str) -> str:
    """Executa código Python recebido como string e retorna o resultado ou erro."""
    try:
        local_vars = {}
        exec(code, {}, local_vars)
        return f"Output: {local_vars}"
    except Exception as e:
        return f"Erro ao executar código:\n{traceback.format_exc()}"

# Ferramenta para rodar o pipeline de filmes
@mcp.tool()
def run_movie_pipeline(args: str = "") -> str:
    """
    Executa o script run_mcp.py com argumentos opcionais e retorna a saída.
    """
    try:
        result = subprocess.run(
            ["python3", "run_mcp.py"] + args.split(),
            capture_output=True,
            text=True,
            timeout=120
        )
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e:
        return f"Erro ao executar run_mcp.py: {e}"

# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"

if __name__ == "__main__":
    print("Iniciando o servidor MCP na porta 6277 (HTTP)...")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=6277)
    print("Servidor MCP finalizado.")