#!/bin/bash
# Deploy com portas alternativas para evitar conflitos

echo "🚀 AI Film Pipeline - Deploy com Portas Alternativas"
echo "====================================================="
echo ""

# Parar processo anterior se existir
echo "🛑 Parando processos anteriores..."
pkill -f start_dagster_with_upload.py 2>/dev/null || true
sleep 2

# Configurar variáveis de ambiente
# COMFYUI_URL será obtido automaticamente via CI/CD ou de arquivo
if [ -f "artifacts/comfyui_url.txt" ]; then
    export COMFYUI_URL=$(head -n 1 artifacts/comfyui_url.txt)
    echo "📡 URL obtida de artifacts: $COMFYUI_URL"
elif [ -n "$COMFYUI_URL" ]; then
    echo "📡 URL obtida de variável de ambiente: $COMFYUI_URL"
else
    echo "⚠️ COMFYUI_URL não configurada!"
    echo "💡 Configure via:"
    echo "   export COMFYUI_URL='https://sua-url.trycloudflare.com'"
    echo "   ou execute via CI/CD que captura automaticamente"
    exit 1
fi

export DAGSTER_WEBSERVER_PORT=3001
export FLASK_PORT=5001

echo "✅ Variáveis configuradas:"
echo "   COMFYUI_URL: $COMFYUI_URL"
echo "   DAGSTER_WEBSERVER_PORT: $DAGSTER_WEBSERVER_PORT"
echo "   FLASK_PORT: $FLASK_PORT"
echo ""

# Navegar para diretório
cd open3d_implementation/orchestration

echo "🚀 Iniciando serviços..."
echo ""

# Iniciar em background
nohup python start_dagster_with_upload.py > ../../logs/deploy.log 2>&1 &

DEPLOY_PID=$!
echo "✅ Serviços iniciados com PID: $DEPLOY_PID"
echo ""

# Aguardar inicialização
echo "⏳ Aguardando serviços iniciarem (30 segundos)..."
sleep 30

# Verificar se está rodando
if ps -p $DEPLOY_PID > /dev/null; then
    echo "✅ Deploy bem-sucedido!"
    echo ""
    echo "📊 Acesse os serviços:"
    echo "   Dagster UI: http://localhost:3001"
    echo "   Flask Upload: http://localhost:5001"
    echo ""
    echo "📝 Ver logs:"
    echo "   tail -f logs/deploy.log"
    echo ""
    echo "🛑 Parar serviços:"
    echo "   pkill -f start_dagster_with_upload.py"
else
    echo "❌ Erro ao iniciar serviços"
    echo "📝 Ver logs:"
    echo "   cat logs/deploy.log"
    exit 1
fi
