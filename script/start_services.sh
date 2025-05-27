#!/bin/bash

# Exportar PATH para incluir diretórios de binários do Python
PATH="/opt/conda/bin:$PATH"

# Iniciar Blender em segundo plano com o addon MCP
if [ -n "$BLENDER_PATH" ] && [ -f "$BLENDER_PATH" ]; then
    echo "Iniciando Blender..."
    "$BLENDER_PATH" --background --python /app/ComfyUI/custom_nodes/BlenderMCP/server.py &
fi

# Iniciar ComfyUI em segundo plano (com suporte a GPU)
if [ -n "$COMFYUI_PATH" ] && [ -d "$COMFYUI_PATH" ]; then
    echo "Iniciando ComfyUI..."
    cd "$COMFYUI_PATH" && python main.py --listen 0.0.0.0 --port 8188 &
fi

# Iniciar a aplicação principal
echo "Iniciando aplicação principal..."
cd /app

echo "Verificando se o gunicorn está disponível..."
which gunicorn || pip install gunicorn

echo "Iniciando servidor gunicorn..."
exec gunicorn --bind 0.0.0.0:8080 --workers 1 --threads 8 --timeout 0 script.run_mcp:app
