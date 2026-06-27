#!/bin/bash
# Script para diagnosticar e corrigir GOOGLE_COLAB_CREDENTIALS

echo "╔═══════════════════════════════════════════════════════════════════════════════╗"
echo "║         🔧 DIAGNÓSTICO E CORREÇÃO DO GOOGLE_COLAB_CREDENTIALS                ║"
echo "╚═══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Verificar se temos arquivo de service account
SERVICE_ACCOUNT_FILES=$(find . -name "*service*account*.json" -o -name "*credentials*.json" 2>/dev/null | grep -v node_modules | grep -v venv | grep -v ".git")

if [ -n "$SERVICE_ACCOUNT_FILES" ]; then
    echo "✅ Arquivos de Service Account encontrados:"
    echo "$SERVICE_ACCOUNT_FILES"
    echo ""
    
    # Pegar o primeiro arquivo
    FIRST_FILE=$(echo "$SERVICE_ACCOUNT_FILES" | head -1)
    echo "📄 Usando arquivo: $FIRST_FILE"
    echo ""
    
    # Validar JSON
    if jq empty "$FIRST_FILE" 2>/dev/null; then
        echo "✅ JSON válido!"
        echo ""
        
        # Mostrar info do service account
        PROJECT_ID=$(jq -r '.project_id // "N/A"' "$FIRST_FILE")
        CLIENT_EMAIL=$(jq -r '.client_email // "N/A"' "$FIRST_FILE")
        
        echo "📊 Informações da Service Account:"
        echo "   Project ID: $PROJECT_ID"
        echo "   Client Email: $CLIENT_EMAIL"
        echo ""
        
        # Perguntar se quer configurar
        read -p "❓ Deseja configurar este arquivo como GOOGLE_COLAB_CREDENTIALS? (s/N): " CONFIRM
        
        if [ "$CONFIRM" = "s" ] || [ "$CONFIRM" = "S" ]; then
            echo ""
            echo "📤 Configurando secret..."
            
            gh secret set GOOGLE_COLAB_CREDENTIALS < "$FIRST_FILE"
            
            if [ $? -eq 0 ]; then
                echo "✅ Secret GOOGLE_COLAB_CREDENTIALS configurado com sucesso!"
                echo ""
                echo "📋 Próximos passos:"
                echo "   1. Verificar se notebook foi compartilhado com: $CLIENT_EMAIL"
                echo "   2. Verificar Drive API habilitada no projeto: $PROJECT_ID"
                echo "   3. Re-executar pipeline"
            else
                echo "❌ Erro ao configurar secret"
            fi
        else
            echo "❌ Configuração cancelada"
        fi
    else
        echo "❌ JSON inválido no arquivo: $FIRST_FILE"
    fi
else
    echo "❌ Nenhum arquivo de Service Account encontrado"
    echo ""
    echo "📖 Para criar uma Service Account:"
    echo "   1. Acesse: https://console.cloud.google.com/iam-admin/serviceaccounts"
    echo "   2. Selecione seu projeto"
    echo "   3. Clique 'CREATE SERVICE ACCOUNT'"
    echo "   4. Dê um nome (ex: colab-executor)"
    echo "   5. Em 'Grant this service account access', selecione: Editor"
    echo "   6. Clique 'DONE'"
    echo "   7. Clique no service account criado"
    echo "   8. Aba 'KEYS' → 'ADD KEY' → 'Create new key' → JSON"
    echo "   9. Baixe o arquivo JSON"
    echo "  10. Coloque na pasta do projeto"
    echo "  11. Execute este script novamente"
    echo ""
    echo "⚠️  IMPORTANTE:"
    echo "   - Habilite Drive API no projeto GCP"
    echo "   - Compartilhe notebook Colab com email da service account"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
