#!/bin/bash

echo "🎮 Colab GPU Setup - Configuração Automática"
echo "=============================================="
echo ""

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

BASE_DIR="/usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP"

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] ⚠️  $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ❌ $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')] ℹ️  $1${NC}"
}

# Verificar se estamos no diretório correto
cd "$BASE_DIR" || {
    error "Não foi possível acessar $BASE_DIR"
    exit 1
}

echo ""
log "📋 Verificando configuração atual..."

# Verificar se gh CLI está instalado
if ! command -v gh &> /dev/null; then
    error "GitHub CLI não encontrado. Instale com:"
    echo "  brew install gh"
    echo "  gh auth login"
    exit 1
fi

# Verificar se estamos autenticados
if ! gh auth status &> /dev/null; then
    error "Não autenticado no GitHub. Execute:"
    echo "  gh auth login"
    exit 1
fi

echo ""
log "🔑 Verificando secrets existentes..."

# Verificar secrets existentes
EXISTING_SECRETS=$(gh secret list 2>/dev/null)
if [ $? -ne 0 ]; then
    error "Erro ao listar secrets. Verifique se você tem acesso ao repositório."
    exit 1
fi

# Verificar se COMFYUI_FALLBACK_URL existe
if echo "$EXISTING_SECRETS" | grep -q "COMFYUI_FALLBACK_URL"; then
    log "✅ COMFYUI_FALLBACK_URL já configurado"
    COMFYUI_FALLBACK_EXISTS=true
else
    warn "COMFYUI_FALLBACK_URL não encontrado"
    COMFYUI_FALLBACK_EXISTS=false
fi

# Verificar se COMFYUI_URL_GIST_ID existe
if echo "$EXISTING_SECRETS" | grep -q "COMFYUI_URL_GIST_ID"; then
    log "✅ COMFYUI_URL_GIST_ID já configurado"
    GIST_ID_EXISTS=true
else
    warn "COMFYUI_URL_GIST_ID não encontrado"
    GIST_ID_EXISTS=false
fi

echo ""
log "📝 Próximos passos para configuração do Colab GPU:"
echo ""

echo "┌─────────────────────────────────────────────────────────────┐"
echo "│                    🎮 SETUP COLAB GPU                        │"
echo "└─────────────────────────────────────────────────────────────┘"

echo ""
echo "1️⃣  📝 CRIAR NOTEBOOK COLAB:"
echo "   └─> Acesse: https://colab.research.google.com/"
echo "   └─> File → Open notebook → GitHub"
echo "   └─> URL: https://github.com/Patricia7sp/AI_film"
echo "   └─> Arquivo: colab_comfyui_gpu_notebook.json"
echo ""

echo "2️⃣  🔑 CRIAR TOKEN GITHUB:"
echo "   └─> Acesse: https://github.com/settings/tokens"
echo "   └─> Generate new token (classic)"
echo "   └─> Nome: 'ComfyUI Colab GPU'"
echo "   └─> Permissões: apenas 'gist'"
echo "   └─> COPIE o token gerado"
echo ""

echo "3️⃣  ⚙️  CONFIGURAR NOTEBOOK:"
echo "   └─> Runtime → Change runtime type → GPU"
echo "   └─> Substitua 'ghp_YOUR_TOKEN_HERE' pelo seu token"
echo "   └─> Runtime → Run all"
echo ""

echo "4️⃣  📡 COPIAR GIST ID:"
echo "   └─> Aguarde o notebook executar completamente"
echo "   └─> Copie o GIST ID da saída (formato: ghp_...)"
echo ""

echo "5️⃣  🔐 CONFIGURAR SECRET:"
echo "   └─> Execute aqui no terminal:"
echo ""

if [ "$GIST_ID_EXISTS" = false ]; then
    echo "   # Configure o Gist ID (após executar o Colab):"
    echo -e "   ${YELLOW}gh secret set COMFYUI_URL_GIST_ID --body \"SEU_GIST_ID_AQUI\"${NC}"
    echo ""
fi

if [ "$COMFYUI_FALLBACK_EXISTS" = false ]; then
    echo "   # Configure URL de fallback (opcional):"
    echo -e "   ${YELLOW}gh secret set COMFYUI_FALLBACK_URL --body \"https://seu-url.trycloudflare.com\"${NC}"
    echo ""
fi

echo "6️⃣  ✅ TESTAR INTEGRAÇÃO:"
echo "   └─> Execute um commit de teste:"
echo "      git commit --allow-empty -m \"test: colab gpu setup\""
echo "      git push origin main"
echo ""
echo "   └─> Acompanhe no GitHub Actions:"
echo "      gh run list --limit 3"
echo ""

echo "┌─────────────────────────────────────────────────────────────┐"
echo "│                 📊 STATUS ATUAL                              │"
echo "└─────────────────────────────────────────────────────────────┘"

echo ""
if [ "$COMFYUI_FALLBACK_EXISTS" = true ]; then
    echo "✅ COMFYUI_FALLBACK_URL: Configurado"
else
    echo "❌ COMFYUI_FALLBACK_URL: Pendente"
fi

if [ "$GIST_ID_EXISTS" = true ]; then
    echo "✅ COMFYUI_URL_GIST_ID: Configurado"
else
    echo "❌ COMFYUI_URL_GIST_ID: Pendente"
fi

echo "✅ Colab Notebook: Pronto (colab_comfyui_gpu_notebook.json)"
echo "✅ Documentação: Completa (COLAB_GPU_SETUP.md)"

echo ""
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│                 🎯 PRÓXIMOS PASSOS                           │"
echo "└─────────────────────────────────────────────────────────────┘"

echo ""
echo "1. 📝 Abra o notebook Colab (link acima)"
echo "2. 🔑 Crie o token GitHub"
echo "3. ⚙️ Configure e execute o notebook"
echo "4. 📡 Copie o Gist ID gerado"
echo "5. 🔐 Configure os secrets no GitHub"
echo "6. ✅ Teste com um commit"
echo ""

info "Quando terminar, execute novamente este script para verificar o status!"
echo ""
warn "Mantenha o Colab rodando para ter GPU disponível (~12 horas)"
echo ""
log "Setup Colab GPU preparado! 🚀"
