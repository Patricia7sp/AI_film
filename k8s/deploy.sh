#!/bin/bash
# Script de deploy completo para Kubernetes

set -e

echo "🚀 AI Film Pipeline - Kubernetes Deployment"
echo "==========================================="
echo ""

# Cores para output
RED='\033[0:31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função para printar com cor
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Verificar se kubectl está instalado
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl não encontrado. Por favor, instale kubectl primeiro."
    exit 1
fi

# Verificar conexão com cluster
if ! kubectl cluster-info &> /dev/null; then
    print_error "Não foi possível conectar ao cluster Kubernetes."
    print_warning "Certifique-se de que o cluster está rodando (minikube start, k3s, etc.)"
    exit 1
fi

print_status "Conectado ao cluster Kubernetes"

# 1. Criar namespace
echo ""
echo "📦 Criando namespace..."
kubectl apply -f namespace.yaml
print_status "Namespace 'ai-film' criado"

# 2. Criar secrets e configmaps
echo ""
echo "🔐 Criando secrets e configmaps..."
kubectl apply -f secrets/secrets.yaml
print_status "Secrets e ConfigMaps criados"

# 3. Criar PersistentVolumeClaims
echo ""
echo "💾 Criando PersistentVolumeClaims..."
kubectl apply -f storage/persistent-volumes.yaml
print_status "PVCs criados"

# Aguardar PVCs ficarem bound
echo "⏳ Aguardando PVCs ficarem bound..."
kubectl wait --for=condition=Bound pvc --all -n ai-film --timeout=120s || print_warning "Alguns PVCs podem não estar bound ainda"

# 4. Deploy data layer (PostgreSQL, Redis)
echo ""
echo "🗄️  Deploying data layer..."
kubectl apply -f data-layer/postgresql.yaml
kubectl apply -f data-layer/redis.yaml
print_status "Data layer deployed"

# Aguardar PostgreSQL e Redis ficarem prontos
echo "⏳ Aguardando PostgreSQL ficar pronto..."
kubectl wait --for=condition=ready pod -l app=postgresql -n ai-film --timeout=180s

echo "⏳ Aguardando Redis ficar pronto..."
kubectl wait --for=condition=ready pod -l app=redis -n ai-film --timeout=120s

# 5. Deploy processing layer (ComfyUI, Blender, FFmpeg)
echo ""
echo "🎨 Deploying processing layer..."
kubectl apply -f processing-layer/comfyui.yaml
kubectl apply -f processing-layer/blender.yaml
kubectl apply -f processing-layer/ffmpeg.yaml
print_status "Processing layer deployed"

# 6. Deploy application layer (Dagster, LangGraph, Flask)
echo ""
echo "🚀 Deploying application layer..."
kubectl apply -f app-layer/dagster.yaml
kubectl apply -f app-layer/langgraph.yaml
kubectl apply -f app-layer/flask-upload.yaml
print_status "Application layer deployed"

# 7. Deploy ingress
echo ""
echo "🌐 Deploying ingress..."
kubectl apply -f ingress.yaml
print_status "Ingress deployed"

# 8. Deploy autoscaling (HPA)
echo ""
echo "📈 Deploying autoscaling..."
kubectl apply -f autoscaling/hpa.yaml
print_status "HPA deployed"

# Mostrar status
echo ""
echo "📊 Status do deployment:"
echo "======================="
kubectl get all -n ai-film

echo ""
echo "💾 PersistentVolumeClaims:"
kubectl get pvc -n ai-film

echo ""
echo "🔐 Secrets e ConfigMaps:"
kubectl get secrets,configmaps -n ai-film

echo ""
echo "✅ Deploy completo!"
echo ""
echo "📋 Próximos passos:"
echo "1. Aguarde todos os pods ficarem Running:"
echo "   kubectl get pods -n ai-film -w"
echo ""
echo "2. Acesse Dagster UI:"
echo "   kubectl port-forward svc/dagster 3000:3000 -n ai-film"
echo "   Abra: http://localhost:3000"
echo ""
echo "3. Acesse Flask Upload:"
echo "   kubectl port-forward svc/flask-upload 5000:5000 -n ai-film"
echo "   Abra: http://localhost:5000"
echo ""
echo "4. Ver logs:"
echo "   kubectl logs -f deployment/dagster -n ai-film"
echo ""
echo "5. Atualizar ComfyUI URL:"
echo "   kubectl edit configmap comfyui-config -n ai-film"
echo ""
