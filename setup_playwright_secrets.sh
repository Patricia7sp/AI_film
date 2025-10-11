#!/bin/bash
# ============================================================
# 🎭 Setup Playwright Secrets - Configuração Interativa
# ============================================================

set -e

echo "============================================================"
echo "🎭 CONFIGURAÇÃO PLAYWRIGHT COLAB AUTOMATION"
echo "============================================================"
echo ""

# Verificar se gh CLI está instalado
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) não está instalado"
    echo "💡 Instale: https://cli.github.com/"
    exit 1
fi

echo "✅ GitHub CLI encontrado"
echo ""

# Verificar autenticação
if ! gh auth status &> /dev/null; then
    echo "❌ Você não está autenticado no GitHub CLI"
    echo "💡 Execute: gh auth login"
    exit 1
fi

echo "✅ Autenticado no GitHub"
echo ""

# ============================================================
# PASSO 1: Email Google
# ============================================================

echo "============================================================"
echo "📧 PASSO 1: Email Google"
echo "============================================================"
echo ""

# Verificar se já existe
if gh secret list | grep -q "GOOGLE_EMAIL"; then
    echo "⚠️ GOOGLE_EMAIL já está configurado"
    read -p "Deseja reconfigurar? (s/N): " RECONFIG_EMAIL
    if [[ ! "$RECONFIG_EMAIL" =~ ^[Ss]$ ]]; then
        echo "✅ Mantendo GOOGLE_EMAIL existente"
        SKIP_EMAIL=true
    fi
fi

if [[ "$SKIP_EMAIL" != "true" ]]; then
    read -p "Digite seu email Google: " GOOGLE_EMAIL
    
    if [[ -z "$GOOGLE_EMAIL" ]]; then
        echo "❌ Email não pode estar vazio"
        exit 1
    fi
    
    echo "📧 Configurando GOOGLE_EMAIL..."
    gh secret set GOOGLE_EMAIL --body "$GOOGLE_EMAIL"
    echo "✅ GOOGLE_EMAIL configurado!"
fi

echo ""

# ============================================================
# PASSO 2: App Password
# ============================================================

echo "============================================================"
echo "🔑 PASSO 2: Google App Password"
echo "============================================================"
echo ""

# Verificar se já existe
if gh secret list | grep -q "GOOGLE_PASSWORD"; then
    echo "⚠️ GOOGLE_PASSWORD já está configurado"
    read -p "Deseja reconfigurar? (s/N): " RECONFIG_PASS
    if [[ ! "$RECONFIG_PASS" =~ ^[Ss]$ ]]; then
        echo "✅ Mantendo GOOGLE_PASSWORD existente"
        SKIP_PASSWORD=true
    fi
fi

if [[ "$SKIP_PASSWORD" != "true" ]]; then
    echo "⚠️ IMPORTANTE: Use App Password, NÃO sua senha real!"
    echo ""
    echo "Como criar App Password:"
    echo "1. Acesse: https://myaccount.google.com/apppasswords"
    echo "2. Nome: 'GitHub Actions Colab'"
    echo "3. Copie o password gerado (16 caracteres)"
    echo ""
    
    read -p "Pressione ENTER para abrir o link no navegador..."
    
    # Tentar abrir no navegador
    if command -v open &> /dev/null; then
        open "https://myaccount.google.com/apppasswords"
    elif command -v xdg-open &> /dev/null; then
        xdg-open "https://myaccount.google.com/apppasswords"
    fi
    
    echo ""
    read -sp "Cole o App Password aqui: " GOOGLE_PASSWORD
    echo ""
    
    if [[ -z "$GOOGLE_PASSWORD" ]]; then
        echo "❌ Password não pode estar vazio"
        exit 1
    fi
    
    echo "🔑 Configurando GOOGLE_PASSWORD..."
    gh secret set GOOGLE_PASSWORD --body "$GOOGLE_PASSWORD"
    echo "✅ GOOGLE_PASSWORD configurado!"
fi

echo ""

# ============================================================
# VERIFICAÇÃO
# ============================================================

echo "============================================================"
echo "✅ VERIFICAÇÃO DOS SECRETS"
echo "============================================================"
echo ""

echo "Secrets Google configurados:"
gh secret list | grep GOOGLE

echo ""

# ============================================================
# EXECUTAR WORKFLOW
# ============================================================

echo "============================================================"
echo "🚀 PRONTO PARA EXECUTAR!"
echo "============================================================"
echo ""

read -p "Deseja executar o workflow Playwright agora? (S/n): " RUN_NOW

if [[ ! "$RUN_NOW" =~ ^[Nn]$ ]]; then
    echo ""
    echo "🎭 Executando workflow Playwright..."
    
    gh workflow run "colab-playwright-trigger.yml"
    
    echo ""
    echo "✅ Workflow iniciado!"
    echo ""
    echo "Acompanhe a execução:"
    echo "  gh run watch"
    echo ""
    echo "Ou veja no navegador:"
    echo "  https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/actions"
    echo ""
    
    read -p "Deseja acompanhar a execução agora? (S/n): " WATCH_NOW
    
    if [[ ! "$WATCH_NOW" =~ ^[Nn]$ ]]; then
        sleep 2
        gh run watch
    fi
else
    echo ""
    echo "✅ Secrets configurados!"
    echo ""
    echo "Para executar manualmente:"
    echo "  gh workflow run 'colab-playwright-trigger.yml'"
    echo "  gh run watch"
fi

echo ""
echo "============================================================"
echo "✅ CONFIGURAÇÃO COMPLETA!"
echo "============================================================"
