#!/bin/bash

echo "🚀 Iniciando Minikube..."
echo "================================"

# Verificar se Docker está rodando
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker não está rodando!"
    echo "💡 Abra o Docker Desktop e tente novamente"
    exit 1
fi

echo "✅ Docker está rodando"

# Iniciar minikube em background
echo "⏳ Iniciando minikube (pode demorar 2-3 minutos)..."
minikube start --driver=docker > /tmp/minikube_start.log 2>&1 &
MINIKUBE_PID=$!

# Aguardar com feedback
for i in {1..60}; do
    if minikube status > /dev/null 2>&1; then
        echo ""
        echo "✅ Minikube iniciado com sucesso!"
        break
    fi
    echo -n "."
    sleep 3
done

# Verificar se iniciou
if ! minikube status > /dev/null 2>&1; then
    echo ""
    echo "❌ Minikube não iniciou. Ver logs:"
    cat /tmp/minikube_start.log
    exit 1
fi

# Mostrar status
echo ""
echo "📊 Status do Minikube:"
minikube status

# Verificar se kubectl config existe
if [ ! -f ~/.kube/config ]; then
    echo "❌ Arquivo ~/.kube/config não encontrado!"
    exit 1
fi

echo ""
echo "✅ Arquivo kubectl config encontrado"

# Atualizar secret do GitHub
echo ""
echo "🔐 Atualizando secret KUBE_CONFIG no GitHub..."
cat ~/.kube/config | base64 | gh secret set KUBE_CONFIG

if [ $? -eq 0 ]; then
    echo "✅ Secret KUBE_CONFIG atualizado com sucesso!"
else
    echo "❌ Erro ao atualizar secret"
    exit 1
fi

# Verificar
echo ""
echo "📋 Secrets do GitHub:"
gh secret list | grep KUBE_CONFIG

echo ""
echo "================================"
echo "✅ Setup completo!"
echo ""
echo "💡 Próximos passos:"
echo "1. kubectl get nodes"
echo "2. kubectl cluster-info"
echo "3. cd k8s && ./deploy.sh"
