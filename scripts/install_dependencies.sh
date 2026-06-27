#!/bin/bash
# Script para instalar dependências faltantes do AI Film Pipeline

echo "📦 Instalando dependências faltantes..."
echo ""

# Instalar nova biblioteca do Gemini
echo "🔧 Instalando google-genai (nova biblioteca)..."
pip3 install google-genai

# Verificar instalação
if python3 -c "from google import genai" 2>/dev/null; then
    echo "✅ google-genai instalado com sucesso!"
else
    echo "❌ Falha ao instalar google-genai"
    exit 1
fi

echo ""
echo "✅ Todas as dependências instaladas!"
echo ""
echo "🔍 Execute o diagnóstico novamente:"
echo "   python3 scripts/diagnose_system.py"
