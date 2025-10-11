#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║   🎮 Setup Automático ComfyUI + Cloudflare (LOCAL)    ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Diretório base
BASE_DIR="/usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP"
COMFYUI_DIR="$BASE_DIR/ComfyUI"
LOG_DIR="$BASE_DIR/logs"

mkdir -p "$LOG_DIR"

# Função para log
log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ❌ $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] ⚠️  $1${NC}"
}

# ============================================================
# 1. INSTALAR COMFYUI
# ============================================================
log "📦 Passo 1/8: Instalando ComfyUI..."

if [ -d "$COMFYUI_DIR" ]; then
    warn "ComfyUI já existe. Pulando instalação."
else
    log "Clonando repositório ComfyUI..."
    cd "$BASE_DIR"
    git clone https://github.com/comfyanonymous/ComfyUI.git
    
    if [ $? -ne 0 ]; then
        error "Falha ao clonar ComfyUI"
        exit 1
    fi
    
    log "Instalando dependências do ComfyUI..."
    cd "$COMFYUI_DIR"
    
    # Criar ambiente virtual se não existir
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    pip install -r requirements.txt
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    
    log "✅ ComfyUI instalado!"
fi

# ============================================================
# 2. INICIAR COMFYUI EM BACKGROUND
# ============================================================
log "🚀 Passo 2/8: Iniciando ComfyUI em background..."

cd "$COMFYUI_DIR"

# Verificar se já está rodando
if lsof -ti:8188 > /dev/null 2>&1; then
    warn "ComfyUI já está rodando na porta 8188"
    COMFYUI_PID=$(lsof -ti:8188)
    log "PID do ComfyUI: $COMFYUI_PID"
else
    # Ativar venv
    source venv/bin/activate
    
    # Iniciar ComfyUI
    nohup python main.py --listen --port 8188 > "$LOG_DIR/comfyui.log" 2>&1 &
    COMFYUI_PID=$!
    
    log "ComfyUI iniciado com PID: $COMFYUI_PID"
    echo $COMFYUI_PID > "$LOG_DIR/comfyui.pid"
fi

# ============================================================
# 3. LOOP VERIFICANDO curl http://localhost:8188
# ============================================================
log "⏳ Passo 3/8: Verificando se ComfyUI está respondendo (até 60s)..."

COMFYUI_READY=false
for i in {1..30}; do
    if curl -s http://localhost:8188 > /dev/null 2>&1; then
        log "✅ ComfyUI está respondendo!"
        COMFYUI_READY=true
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

if [ "$COMFYUI_READY" = false ]; then
    error "ComfyUI não respondeu após 60 segundos"
    echo "📋 Últimas linhas do log:"
    tail -20 "$LOG_DIR/comfyui.log"
    exit 1
fi

# ============================================================
# 4. PRÉ-CHECK ANTES DO CLOUDFLARE
# ============================================================
log "🔍 Passo 4/8: Pré-check do ComfyUI..."

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8188)
if [ "$HTTP_CODE" = "200" ]; then
    log "✅ ComfyUI está acessível (HTTP $HTTP_CODE)"
else
    warn "ComfyUI retornou HTTP $HTTP_CODE"
fi

# ============================================================
# 5. INICIAR CLOUDFLARED EM BACKGROUND
# ============================================================
log "📡 Passo 5/8: Instalando e iniciando Cloudflare Tunnel..."

# Verificar se cloudflared está instalado
if ! command -v cloudflared &> /dev/null; then
    log "Instalando cloudflared..."
    
    # Detectar arquitetura
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz"
    elif [ "$ARCH" = "arm64" ]; then
        CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz"
    else
        error "Arquitetura não suportada: $ARCH"
        exit 1
    fi
    
    cd /tmp
    curl -L "$CLOUDFLARED_URL" -o cloudflared.tgz
    tar -xzf cloudflared.tgz
    sudo mv cloudflared /usr/local/bin/
    sudo chmod +x /usr/local/bin/cloudflared
    
    log "✅ cloudflared instalado"
fi

# Verificar se cloudflared já está rodando
if pgrep -f "cloudflared tunnel" > /dev/null 2>&1; then
    warn "cloudflared já está rodando"
    CLOUDFLARED_PID=$(pgrep -f "cloudflared tunnel")
else
    # Iniciar cloudflared
    nohup cloudflared tunnel --url http://localhost:8188 > "$LOG_DIR/cloudflared.log" 2>&1 &
    CLOUDFLARED_PID=$!
    
    log "Cloudflared iniciado com PID: $CLOUDFLARED_PID"
    echo $CLOUDFLARED_PID > "$LOG_DIR/cloudflared.pid"
fi

# ============================================================
# 6. LOOP 90x COM PROGRESSO DETALHADO
# ============================================================
log "⏳ Passo 6/8: Aguardando URL do Cloudflare (até 3 minutos)..."

URL=""
for i in {1..90}; do
    sleep 2
    
    # Mostrar progresso a cada 10 tentativas
    if [ $((i % 10)) -eq 0 ]; then
        elapsed=$((i * 2))
        log "Tentativa $i/90... (${elapsed}s passados)"
        log "Últimas 3 linhas do log:"
        tail -3 "$LOG_DIR/cloudflared.log" | sed 's/^/   /'
    fi
    
    # Verificar se URL foi gerada
    if grep -q "trycloudflare.com" "$LOG_DIR/cloudflared.log"; then
        URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG_DIR/cloudflared.log" | head -1)
        log "✅ URL gerada: $URL"
        break
    fi
    
    # Verificar se processo ainda está vivo
    if ! ps -p $CLOUDFLARED_PID > /dev/null 2>&1; then
        error "Cloudflared morreu!"
        echo "📋 Log do cloudflared:"
        cat "$LOG_DIR/cloudflared.log"
        exit 1
    fi
done

if [ -z "$URL" ]; then
    error "Falha ao obter URL após 180 segundos"
    echo "📋 Log completo do cloudflared:"
    cat "$LOG_DIR/cloudflared.log"
    exit 1
fi

# ============================================================
# 7. VERIFICAR SE CLOUDFLARED ESTÁ VIVO
# ============================================================
log "🔍 Passo 7/8: Verificando saúde do cloudflared..."

if ps -p $CLOUDFLARED_PID > /dev/null 2>&1; then
    log "✅ Cloudflared está ativo (PID: $CLOUDFLARED_PID)"
else
    error "Cloudflared não está mais rodando!"
    exit 1
fi

# Testar conectividade externa
log "Testando conectividade da URL pública..."
for i in {1..5}; do
    if curl -s -f "$URL" > /dev/null 2>&1; then
        log "✅ URL está acessível externamente!"
        break
    fi
    warn "Tentativa $i/5 falhou, aguardando..."
    sleep 3
done

# ============================================================
# 8. CAPTURAR URL E SALVAR
# ============================================================
log "💾 Passo 8/8: Salvando URL capturada..."

# Salvar em arquivo local
echo "$URL" > "$LOG_DIR/comfyui_url.txt"
echo "$(date)" >> "$LOG_DIR/comfyui_url.txt"

log "URL salva em: $LOG_DIR/comfyui_url.txt"

# Tentar enviar para Gist (se token estiver configurado)
if [ -n "$GITHUB_TOKEN" ]; then
    log "Enviando URL para GitHub Gist..."
    
    python3 << EOF
import requests
import json
import os

github_token = os.getenv('GITHUB_TOKEN')
gist_id = os.getenv('COMFYUI_URL_GIST_ID')
url = "$URL"

headers = {
    'Authorization': f'token {github_token}',
    'Accept': 'application/vnd.github.v3+json'
}

data = {
    "description": "ComfyUI URL - Local",
    "public": False,
    "files": {
        "comfyui_url.json": {
            "content": json.dumps({
                "url": url,
                "updated_at": "$(date)",
                "source": "local_setup"
            }, indent=2)
        }
    }
}

if gist_id:
    r = requests.patch(f'https://api.github.com/gists/{gist_id}', headers=headers, json=data)
else:
    r = requests.post('https://api.github.com/gists', headers=headers, json=data)

if r.status_code in [200, 201]:
    gist_id = r.json()['id']
    print(f"✅ Gist atualizado: https://gist.github.com/{gist_id}")
    if not os.getenv('COMFYUI_URL_GIST_ID'):
        print(f"\n⚠️ Execute: export COMFYUI_URL_GIST_ID='{gist_id}'")
else:
    print(f"❌ Erro ao atualizar Gist: {r.status_code}")
EOF
else
    warn "GITHUB_TOKEN não configurado. Pulando envio para Gist."
fi

# ============================================================
# RESUMO FINAL
# ============================================================
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║              ✅ SETUP COMPLETO!                        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "📊 RESUMO:"
echo "─────────────────────────────────────────────────────────"
echo "🎮 ComfyUI PID:      $COMFYUI_PID"
echo "📡 Cloudflared PID:  $CLOUDFLARED_PID"
echo "🌐 URL Pública:      $URL"
echo "📝 Logs em:          $LOG_DIR/"
echo ""
echo "📋 COMANDOS ÚTEIS:"
echo "─────────────────────────────────────────────────────────"
echo "# Ver logs do ComfyUI:"
echo "  tail -f $LOG_DIR/comfyui.log"
echo ""
echo "# Ver logs do Cloudflare:"
echo "  tail -f $LOG_DIR/cloudflared.log"
echo ""
echo "# Parar tudo:"
echo "  kill $COMFYUI_PID $CLOUDFLARED_PID"
echo ""
echo "# Configurar URL no GitHub:"
echo "  gh secret set COMFYUI_FALLBACK_URL --body '$URL'"
echo ""
echo "════════════════════════════════════════════════════════"
echo "🎉 ComfyUI está rodando e acessível via: $URL"
echo "════════════════════════════════════════════════════════"
