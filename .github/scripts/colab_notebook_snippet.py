"""
ADICIONE ESTE CÓDIGO AO FINAL DO SEU NOTEBOOK DO COLAB
https://colab.research.google.com/drive/1bfDjw5JGeqExdsUWYM41txvqlCGzOF99

Este código captura a URL do Cloudflare e envia para o GitHub Actions
"""

import re
import time
import requests
import os

def capture_and_send_comfyui_url():
    """
    Captura URL do Cloudflare e envia para GitHub Actions
    """
    print("="*70)
    print("🎬 CAPTURANDO URL DO COMFYUI PARA GITHUB ACTIONS")
    print("="*70)
    
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
    
    # 4. Salvar em arquivo (para GitHub Actions ler)
    try:
        with open('/content/comfyui_url.txt', 'w') as f:
            f.write(tunnel_url)
        print("✅ URL salva em /content/comfyui_url.txt")
    except Exception as e:
        print(f"❌ Erro ao salvar arquivo: {e}")
    
    # 5. Enviar para webhook (se configurado)
    webhook_url = os.getenv('COMFYUI_WEBHOOK_URL')
    if webhook_url:
        try:
            response = requests.post(
                webhook_url,
                json={
                    "url": tunnel_url,
                    "notebook_id": "1bfDjw5JGeqExdsUWYM41txvqlCGzOF99",
                    "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "status": "ready"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                print("✅ URL enviada para webhook")
            else:
                print(f"⚠️ Webhook retornou status {response.status_code}")
        except Exception as e:
            print(f"⚠️ Erro ao enviar para webhook: {e}")
    else:
        print("ℹ️ Webhook não configurado (opcional)")
    
    # 6. Exibir instruções
    print("\n" + "="*70)
    print("✅ CONFIGURAÇÃO COMPLETA!")
    print("="*70)
    print(f"\n🎯 ComfyUI URL: {tunnel_url}")
    print("\n📋 Para usar no GitHub Actions:")
    print("1. Configure o secret COMFYUI_FALLBACK_URL com esta URL")
    print("2. Ou configure um webhook para captura automática")
    print("\n💡 Esta URL é válida enquanto este notebook estiver rodando")
    print("="*70 + "\n")

# Executar automaticamente
capture_and_send_comfyui_url()
