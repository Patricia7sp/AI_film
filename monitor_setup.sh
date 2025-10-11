#!/bin/bash

LOG_DIR="/usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP/logs"

echo "🔍 Monitorando setup do ComfyUI..."
echo ""

# Verificar se ComfyUI está rodando
if [ -f "$LOG_DIR/comfyui.pid" ]; then
    PID=$(cat "$LOG_DIR/comfyui.pid")
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ ComfyUI rodando (PID: $PID)"
    else
        echo "❌ ComfyUI não está rodando"
    fi
fi

# Verificar se Cloudflared está rodando
if [ -f "$LOG_DIR/cloudflared.pid" ]; then
    PID=$(cat "$LOG_DIR/cloudflared.pid")
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ Cloudflared rodando (PID: $PID)"
    else
        echo "❌ Cloudflared não está rodando"
    fi
fi

# Mostrar URL se disponível
if [ -f "$LOG_DIR/comfyui_url.txt" ]; then
    echo ""
    echo "🌐 URL Capturada:"
    cat "$LOG_DIR/comfyui_url.txt"
fi

echo ""
echo "📋 Últimas 10 linhas do log do ComfyUI:"
echo "──────────────────────────────────────"
if [ -f "$LOG_DIR/comfyui.log" ]; then
    tail -10 "$LOG_DIR/comfyui.log"
else
    echo "Log ainda não existe"
fi

echo ""
echo "📋 Últimas 10 linhas do log do Cloudflare:"
echo "──────────────────────────────────────"
if [ -f "$LOG_DIR/cloudflared.log" ]; then
    tail -10 "$LOG_DIR/cloudflared.log"
else
    echo "Log ainda não existe"
fi
