#!/usr/bin/env python3
"""
Script para iniciar ComfyUI no Google Colab automaticamente via API
e obter a URL do túnel Cloudflare
"""

import os
import sys
import time
import json
import requests
from pathlib import Path
from typing import Optional

# Configurações
COLAB_NOTEBOOK_ID = os.getenv('COLAB_NOTEBOOK_ID')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')
MAX_RETRIES = 30
RETRY_DELAY = 10  # segundos


def start_colab_notebook() -> Optional[str]:
    """
    Inicia o notebook do Colab via API do Google Colab
    
    Nota: Requer configuração de credenciais do Google Cloud
    """
    print("🚀 Iniciando Google Colab notebook...")
    
    # TODO: Implementar integração com Google Colab API
    # Por enquanto, retorna URL mock para desenvolvimento
    
    # Alternativa: Usar selenium para automatizar browser
    # ou usar API não oficial do Colab
    
    print("⚠️ Implementação pendente: Integração com Colab API")
    print("💡 Alternativas:")
    print("   1. Usar webhook do Colab para notificar quando estiver pronto")
    print("   2. Usar ngrok/cloudflared localmente")
    print("   3. Usar API do Colab (não oficial)")
    
    return None


def wait_for_comfyui_ready(url: str, max_retries: int = MAX_RETRIES) -> bool:
    """
    Aguarda o ComfyUI estar pronto para receber requisições
    """
    print(f"⏳ Aguardando ComfyUI ficar disponível em: {url}")
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ ComfyUI está pronto! (tentativa {attempt + 1}/{max_retries})")
                return True
        except requests.exceptions.RequestException:
            pass
        
        print(f"⏳ Tentativa {attempt + 1}/{max_retries} - Aguardando {RETRY_DELAY}s...")
        time.sleep(RETRY_DELAY)
    
    print("❌ Timeout: ComfyUI não ficou disponível")
    return False


def get_cloudflare_tunnel_url() -> Optional[str]:
    """
    Obtém a URL do túnel Cloudflare do Colab
    
    Métodos possíveis:
    1. Ler de arquivo compartilhado (Google Drive)
    2. Webhook do Colab para GitHub Actions
    3. API endpoint customizado
    """
    print("🔍 Buscando URL do túnel Cloudflare...")
    
    # Método 1: Ler de arquivo no Google Drive (requer configuração)
    drive_file_path = os.getenv('COMFYUI_URL_FILE_PATH')
    if drive_file_path:
        try:
            with open(drive_file_path, 'r') as f:
                url = f.read().strip()
                if url:
                    print(f"✅ URL encontrada no arquivo: {url}")
                    return url
        except Exception as e:
            print(f"⚠️ Erro ao ler arquivo: {e}")
    
    # Método 2: Usar URL de fallback para testes
    fallback_url = os.getenv('COMFYUI_FALLBACK_URL')
    if fallback_url:
        print(f"⚠️ Usando URL de fallback: {fallback_url}")
        return fallback_url
    
    print("❌ Não foi possível obter URL do ComfyUI")
    return None


def main():
    """
    Função principal para iniciar ComfyUI e obter URL
    """
    print("=" * 60)
    print("🎬 AI FILM PIPELINE - COMFYUI AUTOMATION")
    print("=" * 60)
    
    # Verificar credenciais
    if not COLAB_NOTEBOOK_ID:
        print("⚠️ COLAB_NOTEBOOK_ID não configurado")
        print("💡 Configure o secret no GitHub: COLAB_NOTEBOOK_ID")
    
    # Iniciar Colab (se implementado)
    # start_colab_notebook()
    
    # Obter URL do túnel
    comfyui_url = get_cloudflare_tunnel_url()
    
    if not comfyui_url:
        print("\n❌ ERRO: Não foi possível obter URL do ComfyUI")
        print("\n📋 INSTRUÇÕES PARA CONFIGURAÇÃO:")
        print("1. Execute o notebook do Colab manualmente")
        print("2. Copie a URL do túnel Cloudflare")
        print("3. Configure como secret: COMFYUI_FALLBACK_URL")
        print("4. Ou implemente integração automática com Colab")
        sys.exit(1)
    
    # Verificar se ComfyUI está acessível
    if not wait_for_comfyui_ready(comfyui_url):
        print(f"\n❌ ComfyUI não está acessível em: {comfyui_url}")
        sys.exit(1)
    
    # Exportar URL para GitHub Actions
    print(f"\n✅ ComfyUI URL: {comfyui_url}")
    
    # Escrever output para GitHub Actions
    github_output = os.getenv('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"comfyui_url={comfyui_url}\n")
        print(f"✅ URL exportada para GitHub Actions")
    
    print("\n" + "=" * 60)
    print("✅ COMFYUI PRONTO PARA USO")
    print("=" * 60)


if __name__ == "__main__":
    main()
