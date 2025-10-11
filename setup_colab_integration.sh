#!/bin/bash

echo "╔════════════════════════════════════════════════════════╗"
echo "║   🎮 Setup Integração Colab + GitHub Actions          ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Verificar secrets existentes
echo "📋 Verificando secrets atuais..."
echo ""
gh secret list | grep -i comfyui
echo ""

# Verificar se Gist ID está configurado
GIST_ID=$(gh secret get COMFYUI_URL_GIST_ID 2>/dev/null)
if [ -n "$GIST_ID" ]; then
    echo "✅ Gist ID já configurado: $GIST_ID"
else
    echo "⚠️ Gist ID não configurado"
fi

echo ""
echo "════════════════════════════════════════════════════════"
echo "📝 PRÓXIMOS PASSOS:"
echo "════════════════════════════════════════════════════════"
echo ""

echo "1️⃣ CRIAR PERSONAL ACCESS TOKEN (se ainda não tem)"
echo "   → Acesse: https://github.com/settings/tokens"
echo "   → Generate new token (classic)"
echo "   → Nome: 'ComfyUI Auto Update'"
echo "   → Marque apenas: 'gist'"
echo "   → Generate token e COPIE!"
echo ""

echo "2️⃣ ABRIR NOTEBOOK DO COLAB"
echo "   → URL: https://colab.research.google.com/drive/1bfDjw5JGeqExdsUWYM41txvqlCGzOF99"
echo "   → Runtime → Change runtime type → GPU (T4)"
echo ""

echo "3️⃣ ADICIONAR CÓDIGO NO FINAL DO NOTEBOOK"
echo "   O código está em: .github/scripts/colab_notebook_snippet.py"
echo "   Ou copie daqui:"
echo ""
cat << 'EOF'
# ============================================================
# 🤖 AUTO-UPDATE COMFYUI URL
# ============================================================
import re, time, requests, json

GITHUB_TOKEN = "ghp_SEU_TOKEN_AQUI"  # ⚠️ COLE SEU TOKEN!
GIST_ID = None  # Primeira vez deixe None

def auto_update():
    print("🎬 Capturando URL...")
    time.sleep(30)
    
    with open('/content/cloudflared.log', 'r') as f:
        match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', f.read())
        url = match.group(0) if match else None
    
    if not url:
        print("❌ URL não encontrada")
        return
    
    print(f"✅ URL: {url}")
    
    headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    data = {
        "description": "ComfyUI URL",
        "public": False,
        "files": {"comfyui_url.json": {"content": json.dumps({"url": url, "updated_at": time.strftime('%Y-%m-%d %H:%M:%S')}, indent=2)}}
    }
    
    if GIST_ID:
        r = requests.patch(f'https://api.github.com/gists/{GIST_ID}', headers=headers, json=data)
    else:
        r = requests.post('https://api.github.com/gists', headers=headers, json=data)
    
    if r.status_code in [200, 201]:
        gist_id = r.json()['id']
        print(f"✅ Gist: https://gist.github.com/{gist_id}")
        if not GIST_ID:
            print(f"\n⚠️ COPIE ESTE ID:")
            print(f"   {gist_id}")
            print(f"\n Execute no terminal:")
            print(f"   gh secret set COMFYUI_URL_GIST_ID --body '{gist_id}'")
    else:
        print(f"❌ Erro: {r.status_code}")

auto_update()
EOF

echo ""
echo "4️⃣ EXECUTAR NOTEBOOK PELA PRIMEIRA VEZ"
echo "   → Runtime → Run all"
echo "   → Aguarde ComfyUI iniciar (~3 min)"
echo "   → COPIE o Gist ID da saída"
echo ""

echo "5️⃣ CONFIGURAR GIST ID"
echo "   Execute o comando que aparece no Colab:"
echo "   gh secret set COMFYUI_URL_GIST_ID --body 'SEU_GIST_ID'"
echo ""

echo "6️⃣ ATUALIZAR NOTEBOOK"
echo "   → No notebook, substitua: GIST_ID = None"
echo "   → Por: GIST_ID = 'seu-gist-id'"
echo "   → Salve o notebook"
echo ""

echo "════════════════════════════════════════════════════════"
echo "🎯 TESTE FINAL"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Depois do setup, teste com:"
echo "  git commit --allow-empty -m 'test: CI/CD integration'"
echo "  git push origin feature/test-full-cicd"
echo ""
echo "Acompanhe em:"
echo "  gh run list --limit 3"
echo "  gh run view --log"
echo ""
echo "════════════════════════════════════════════════════════"
echo "✅ Pronto! Siga os passos acima"
echo "════════════════════════════════════════════════════════"
