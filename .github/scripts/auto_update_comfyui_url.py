#!/usr/bin/env python3
"""
Script para atualizar automaticamente a URL do ComfyUI usando GitHub Gist
Este script é executado pelo workflow e atualiza o secret automaticamente
"""

import os
import sys
import json
import time
import requests
from typing import Optional

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO = os.getenv('GITHUB_REPOSITORY', 'Patricia7sp/AI_film')
GIST_ID = os.getenv('COMFYUI_URL_GIST_ID')  # ID do Gist para armazenar URL


def create_or_update_gist(url: str) -> str:
    """
    Cria ou atualiza um Gist com a URL do ComfyUI
    
    Args:
        url: URL do ComfyUI
        
    Returns:
        ID do Gist
    """
    print("📝 Atualizando Gist com URL do ComfyUI...")
    
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    gist_content = {
        "description": "ComfyUI URL - AI Film Pipeline",
        "public": False,
        "files": {
            "comfyui_url.json": {
                "content": json.dumps({
                    "url": url,
                    "updated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "status": "active"
                }, indent=2)
            }
        }
    }
    
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
        print(f"✅ Gist atualizado: https://gist.github.com/{gist_id}")
        return gist_id
    else:
        print(f"❌ Erro ao atualizar Gist: {response.status_code}")
        print(response.text)
        return None


def read_url_from_gist() -> Optional[str]:
    """
    Lê a URL do ComfyUI do Gist
    
    Returns:
        URL ou None
    """
    if not GIST_ID:
        print("⚠️ COMFYUI_URL_GIST_ID não configurado")
        return None
    
    print(f"📖 Lendo URL do Gist: {GIST_ID}")
    
    try:
        response = requests.get(
            f'https://api.github.com/gists/{GIST_ID}',
            headers={'Accept': 'application/vnd.github.v3+json'}
        )
        
        if response.status_code == 200:
            gist_data = response.json()
            content = gist_data['files']['comfyui_url.json']['content']
            data = json.loads(content)
            url = data.get('url')
            
            if url:
                print(f"✅ URL obtida do Gist: {url}")
                return url
        else:
            print(f"⚠️ Erro ao ler Gist: {response.status_code}")
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    return None


def update_github_secret(secret_name: str, secret_value: str) -> bool:
    """
    Atualiza um secret do GitHub usando a API
    
    Args:
        secret_name: Nome do secret
        secret_value: Valor do secret
        
    Returns:
        True se sucesso
    """
    print(f"🔐 Atualizando secret {secret_name}...")
    
    try:
        # Usar gh CLI para atualizar secret
        import subprocess
        
        result = subprocess.run(
            ['gh', 'secret', 'set', secret_name, '--body', secret_value],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ Secret {secret_name} atualizado!")
            return True
        else:
            print(f"❌ Erro ao atualizar secret: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


def wait_for_url_in_gist(max_wait: int = 300) -> Optional[str]:
    """
    Aguarda URL aparecer no Gist (polling)
    
    Args:
        max_wait: Tempo máximo de espera em segundos
        
    Returns:
        URL ou None
    """
    print(f"⏳ Aguardando URL no Gist (máx {max_wait}s)...")
    
    start_time = time.time()
    attempt = 0
    
    while (time.time() - start_time) < max_wait:
        attempt += 1
        url = read_url_from_gist()
        
        if url and url.startswith('https://'):
            return url
        
        print(f"   Tentativa {attempt}... (aguardando)")
        time.sleep(10)
    
    print("⏰ Timeout aguardando URL")
    return None


def main():
    """
    Função principal
    """
    print("=" * 70)
    print("🔄 AUTO UPDATE COMFYUI URL")
    print("=" * 70)
    print()
    
    # Verificar se deve atualizar (quando vem do Colab) ou ler (no workflow)
    mode = os.getenv('MODE', 'read')  # 'read' ou 'write'
    
    if mode == 'write':
        # Modo escrita: Colab envia URL
        url = os.getenv('COMFYUI_URL')
        if not url:
            print("❌ COMFYUI_URL não fornecida")
            sys.exit(1)
        
        gist_id = create_or_update_gist(url)
        if gist_id:
            print(f"\n✅ URL armazenada com sucesso!")
            print(f"Gist ID: {gist_id}")
            # Exportar para GitHub Actions
            github_output = os.getenv('GITHUB_OUTPUT')
            if github_output:
                with open(github_output, 'a') as f:
                    f.write(f"gist_id={gist_id}\n")
        else:
            sys.exit(1)
    
    else:
        # Modo leitura: Workflow lê URL do Gist
        url = wait_for_url_in_gist(max_wait=300)
        
        if not url:
            print("\n❌ Não foi possível obter URL")
            print("\n📋 SOLUÇÕES:")
            print("1. Execute o notebook do Colab")
            print("2. Aguarde o túnel Cloudflare ser criado")
            print("3. A URL será capturada automaticamente")
            sys.exit(1)
        
        # Atualizar secret
        if update_github_secret('COMFYUI_FALLBACK_URL', url):
            print(f"\n✅ URL atualizada automaticamente: {url}")
            
            # Exportar para GitHub Actions
            github_output = os.getenv('GITHUB_OUTPUT')
            if github_output:
                with open(github_output, 'a') as f:
                    f.write(f"url={url}\n")
                    f.write(f"status=success\n")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
