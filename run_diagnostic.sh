#!/bin/bash
# Script para executar diagnóstico do sistema

echo "🔍 Executando diagnóstico do AI Film Pipeline..."
echo ""

cd "$(dirname "$0")"

# Verificar se Python está disponível
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 não encontrado!"
    exit 1
fi

# Executar diagnóstico
python3 scripts/diagnose_system.py

# Verificar se relatório foi gerado
if [ -f "diagnostic_report.json" ]; then
    echo ""
    echo "✅ Diagnóstico completo!"
    echo "📄 Relatório: diagnostic_report.json"
else
    echo ""
    echo "⚠️  Relatório não foi gerado"
fi
