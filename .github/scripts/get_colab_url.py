#!/usr/bin/env python3
"""
Script para capturar a URL do ComfyUI rodando no Colab

Métodos de captura:
1. Via arquivo compartilhado (Google Drive)
2. Via webhook configurado no Colab
3. Via scraping do log do Cloudflare
4. Via variável de ambiente de fallback
"""

import os
import sys
import time
import json
import requests
import re
from typing import Optional

# Configurações
MAX_RETRIES = 30
RETRY_INTERVAL = 10
COLAB_NOTEBOOK_ID = os.getenv('COLAB_NOTEBOOK_ID', '1bfDjw5JGeqExdsUWYM41txvqlCGzOF99')


def get_url_from_webhook() -> Optional[str]:
    """
    Obtém URL via webhook configurado no Colab
    
    No Colab, adicione ao final do notebook:
    ```python
    import requests
    tunnel_url = "https://xxx.trycloudflare.com"
    webhook = "https://seu-webhook.com/comfyui-url"
    requests.post(webhook, json={"url": tunnel_url, "notebook_id": "xxx"})
    ```
    
    Returns:
        URL do ComfyUI ou None
    """
    print("📡 Método 1: Tentando via webhook...")
    
    webhook_url = os.getenv('COMFYUI_WEBHOOK_URL')
    if not webhook_url:
        print("⚠️ COMFYUI_WEBHOOK_URL não configurado")
        return None
    
    try:
        response = requests.get(f"{webhook_url}/latest", timeout=10)
        if response.status_code == 200:
            data = response.json()
            url = data.get('url')
            if url and url.startswith('https://'):
                print(f"✅ URL obtida via webhook: {url}")
                return url
    except Exception as e:
        print(f"⚠️ Erro ao obter via webhook: {e}")
    
    return None


def get_url_from_file() -> Optional[str]:
    """
    Obtém URL de arquivo compartilhado
    
    Returns:
        URL do ComfyUI ou None
    """
    print("📂 Método 2: Tentando via arquivo compartilhado...")
    
    # Possíveis localizações
    possible_paths = [
        os.path.expanduser("~/comfyui_url.txt"),
        "/tmp/comfyui_url.txt",
        "comfyui_url.txt",
        "artifacts/comfyui_url.txt"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    url = f.read().strip().split('\n')[0]
                    if url and url.startswith('https://'):
                        print(f"✅ URL obtida de arquivo: {url}")
                        return url
            except Exception as e:
                print(f"⚠️ Erro ao ler {path}: {e}")
    
    print("⚠️ Nenhum arquivo encontrado")
    return None


def get_url_from_github_secret() -> Optional[str]:
    """
    Obtém URL de secret do GitHub (fallback)
    
    Returns:
        URL do ComfyUI ou None
    """
    print("🔐 Método 3: Tentando via GitHub Secret...")
    
    url = os.getenv('COMFYUI_FALLBACK_URL')
    if url and url.startswith('https://'):
        print(f"✅ URL obtida de secret: {url}")
        print("⚠️ ATENÇÃO: Usando URL de fallback, pode estar desatualizada")
        return url
    
    print("⚠️ COMFYUI_FALLBACK_URL não configurado")
    return None


def parse_cloudflare_log() -> Optional[str]:
    """
    Tenta fazer parse do log do Cloudflare para extrair URL
    
    Returns:
        URL do ComfyUI ou None
    """
    print("📝 Método 4: Tentando parse de log do Cloudflare...")
    
    # Este método requer acesso ao log do Colab
    # Em produção, você implementaria scraping ou API do Colab
    
    print("⚠️ Parse de log não implementado (requer acesso ao Colab)")
    return None


def test_url_connectivity(url: str) -> bool:
    """
    Testa se a URL está acessível
    
    Args:
        url: URL para testar
        
    Returns:
        True se acessível, False caso contrário
    """
    print(f"🧪 Testando conectividade: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print("✅ URL está acessível!")
            return True
        else:
            print(f"⚠️ URL retornou status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erro ao testar URL: {e}")
        return False


def wait_for_url_available(url: str, max_retries: int = MAX_RETRIES) -> bool:
    """
    Aguarda URL ficar disponível
    
    Args:
        url: URL para aguardar
        max_retries: Número máximo de tentativas
        
    Returns:
        True se ficou disponível, False caso contrário
    """
    print(f"⏳ Aguardando URL ficar disponível (max {max_retries} tentativas)...")
    
    for attempt in range(max_retries):
        if test_url_connectivity(url):
            return True
        
        print(f"   Tentativa {attempt + 1}/{max_retries}...")
        time.sleep(RETRY_INTERVAL)
    
    return False


def main():
    """
    Função principal
    """
    print("=" * 70)
    print("🎬 AI FILM PIPELINE - GET COLAB COMFYUI URL")
    print("=" * 70)
    print()
    
    comfyui_url = None
    
    # Tentar múltiplos métodos em ordem de prioridade
    methods = [
        ("Webhook", get_url_from_webhook),
        ("Arquivo", get_url_from_file),
        ("GitHub Secret", get_url_from_github_secret),
        ("Parse Log", parse_cloudflare_log)
    ]
    
    for method_name, method_func in methods:
        print(f"\n{'='*70}")
        print(f"Tentando método: {method_name}")
        print('='*70)
        
        url = method_func()
        
        if url:
            # Testar conectividade
            if test_url_connectivity(url):
                comfyui_url = url
                break
            else:
                print(f"⚠️ URL obtida mas não está acessível, tentando próximo método...")
    
    if not comfyui_url:
        print("\n" + "="*70)
        print("❌ ERRO: Não foi possível obter URL do ComfyUI")
        print("="*70)
        print("\n📋 INSTRUÇÕES:")
        print("1. Verifique se o Colab está rodando")
        print("2. Verifique se o túnel Cloudflare foi criado")
        print("3. Configure um dos métodos de captura:")
        print("   - Webhook: COMFYUI_WEBHOOK_URL")
        print("   - Arquivo: Salve URL em ~/comfyui_url.txt")
        print("   - Secret: COMFYUI_FALLBACK_URL")
        print()
        sys.exit(1)
    
    # Aguardar URL ficar completamente disponível
    if not wait_for_url_available(comfyui_url):
        print(f"\n❌ URL não ficou disponível: {comfyui_url}")
        sys.exit(1)
    
    # Sucesso! Exportar para GitHub Actions
    print("\n" + "="*70)
    print("✅ SUCESSO!")
    print("="*70)
    print(f"\n🎯 ComfyUI URL: {comfyui_url}\n")
    
    # Exportar para GitHub Actions output
    github_output = os.getenv('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"url={comfyui_url}\n")
            f.write(f"status=success\n")
        print("✅ URL exportada para GitHub Actions")
    
    # Salvar em arquivo para próximos steps
    os.makedirs('artifacts', exist_ok=True)
    with open('artifacts/comfyui_url.txt', 'w') as f:
        f.write(f"{comfyui_url}\n")
        f.write(f"Captured at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Notebook ID: {COLAB_NOTEBOOK_ID}\n")
    
    print("✅ URL salva em artifacts/comfyui_url.txt")
    
    # Salvar JSON com metadados
    with open('artifacts/comfyui_info.json', 'w') as f:
        json.dump({
            "url": comfyui_url,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "notebook_id": COLAB_NOTEBOOK_ID,
            "status": "ready"
        }, f, indent=2)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
