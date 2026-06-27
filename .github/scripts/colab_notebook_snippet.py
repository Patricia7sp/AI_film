"""
ADICIONE ESTE CÓDIGO AO FINAL DO SEU NOTEBOOK DO COLAB
https://colab.research.google.com/drive/1bfDjw5JGeqExdsUWYM41txvqlCGzOF99

Este código captura a URL do Cloudflare e envia AUTOMATICAMENTE para o GitHub
"""

import re
import time
import requests
import json
import os

def capture_and_send_comfyui_url_auto():
    """
    Captura URL do Cloudflare e envia AUTOMATICAMENTE para GitHub Gist
    TOTALMENTE AUTOMÁTICO - Não precisa atualizar secret manualmente!
    """
    print("="*70)
    print("🎬 CAPTURA AUTOMÁTICA DE URL - GITHUB ACTIONS")
    print("="*70)
    
    # Configurações (Configure estes valores)
    GITHUB_TOKEN = "your-github-token"  # Criar em: https://github.com/settings/tokens
    GIST_ID = None  # Deixe None na primeira vez, depois atualize com o ID gerado
    
    # 1. Aguardar cloudflared criar o túnel
    print("\n⏳ Aguardando túnel Cloudflare ser criado...")
    time.sleep(30)
    
    # 2. Ler log do cloudflared
    tunnel_url = None
    
    try:
        with open('/content/cloudflared.log', 'r') as f:
            log_content = f.read()
            
            # Procurar URL no log
            match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', log_content)
            if match:
                tunnel_url = match.group(0)
                print(f"✅ URL encontrada: {tunnel_url}")
            else:
                print("⚠️ URL não encontrada no log")
    except Exception as e:
        print(f"❌ Erro ao ler log: {e}")
    
    if not tunnel_url:
        print("❌ Não foi possível capturar URL")
        return
    
    # 3. Testar conectividade
    print(f"\n🧪 Testando conectividade: {tunnel_url}")
    try:
        response = requests.get(tunnel_url, timeout=10)
        if response.status_code == 200:
            print("✅ ComfyUI está acessível!")
        else:
            print(f"⚠️ Status: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Erro ao testar: {e}")
    
    # 4. Enviar para GitHub Gist AUTOMATICAMENTE
    print(f"\n📤 Enviando URL para GitHub Gist...")
    
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    gist_content = {
        "description": "ComfyUI URL - AI Film Pipeline (Auto-Updated)",
        "public": False,
        "files": {
            "comfyui_url.json": {
                "content": json.dumps({
                    "url": tunnel_url,
                    "updated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "status": "active",
                    "notebook_id": "1bfDjw5JGeqExdsUWYM41txvqlCGzOF99"
                }, indent=2)
            }
        }
    }
    
    try:
        if GIST_ID:
            # Atualizar Gist existente
            response = requests.patch(
                f'https://api.github.com/gists/{GIST_ID}',
                headers=headers,
                json=gist_content
            )
        else:
            # Criar novo Gist
            response = requests.post(
                'https://api.github.com/gists',
                headers=headers,
                json=gist_content
            )
        
        if response.status_code in [200, 201]:
            gist_data = response.json()
            gist_id = gist_data['id']
            gist_url = gist_data['html_url']
            
            print(f"✅ URL enviada para GitHub Gist!")
            print(f"   Gist ID: {gist_id}")
            print(f"   Gist URL: {gist_url}")
            
            if not GIST_ID:
                print(f"\n⚠️ IMPORTANTE: Atualize GIST_ID no código:")
                print(f"   GIST_ID = '{gist_id}'")
                print(f"\n   E configure o secret no GitHub:")
                print(f"   gh secret set COMFYUI_URL_GIST_ID --body '{gist_id}'")
        else:
            print(f"❌ Erro ao enviar para Gist: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Erro ao enviar para Gist: {e}")
    
    # 5. Exibir instruções finais
    print("\n" + "="*70)
    print("✅ CONFIGURAÇÃO AUTOMÁTICA COMPLETA!")
    print("="*70)
    print(f"\n🎯 ComfyUI URL: {tunnel_url}")
    print("\n🤖 TOTALMENTE AUTOMÁTICO:")
    print("   ✅ URL capturada do Cloudflare")
    print("   ✅ URL enviada para GitHub Gist")
    print("   ✅ GitHub Actions irá ler automaticamente")
    print("   ✅ Secret será atualizado automaticamente")
    print("\n💡 Esta URL é válida enquanto este notebook estiver rodando")
    print("🔄 A cada execução, a URL é atualizada automaticamente")
    print("="*70 + "\n")

# Executar automaticamente
capture_and_send_comfyui_url_auto()
