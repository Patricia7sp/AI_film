#!/bin/bash
# Script rápido para atualizar URL do Colab e re-executar pipeline

echo "🚀 ATUALIZAÇÃO RÁPIDA - COMFYUI URL"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Verificar se URL foi passada
if [ -z "$1" ]; then
    echo "❌ Erro: URL não fornecida"
    echo ""
    echo "Uso:"
    echo "  bash quick_update.sh https://sua-url.trycloudflare.com"
    echo ""
    echo "Passos:"
    echo "  1. Inicie o notebook do Colab"
    echo "  2. Copie a URL do Cloudflare"
    echo "  3. Execute: bash quick_update.sh <URL>"
    exit 1
fi

URL=$1

echo "📝 Atualizando URL: $URL"
python3 scripts/update_comfyui_url.py "$URL"

echo ""
echo "🧪 Testando conexão..."
python3 scripts/diagnose_system.py

echo ""
echo "📤 Fazendo commit e push..."
git add open3d_implementation/.env
git commit -m "chore: update ComfyUI URL from Colab"
git push

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ ATUALIZAÇÃO COMPLETA!"
echo ""
echo "🚀 Próximo passo:"
echo "   gh workflow run full-auto-colab-pipeline.yml"
echo ""
echo "   Ou acesse:"
echo "   https://github.com/SEU_USUARIO/LANGGRAPH_MCP/actions"
echo "═══════════════════════════════════════════════════════════"
