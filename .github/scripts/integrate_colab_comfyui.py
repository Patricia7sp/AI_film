#!/usr/bin/env python3
"""
Script para integrar automaticamente com Google Colab ComfyUI
Baseado no notebook: https://colab.research.google.com/drive/1bfDjw5JGeqExdsUWYM41txvqlCGzOF99

Funcionalidades:
1. Detecta quando Colab está rodando
2. Obtém URL do túnel Cloudflare automaticamente
3. Atualiza ConfigMap do Kubernetes
4. Reinicia pods do ComfyUI para usar nova URL
"""

import os
import sys
import time
import json
import requests
import subprocess
from typing import Optional, Dict
from pathlib import Path

# Configurações
COLAB_NOTEBOOK_ID = os.getenv('COLAB_NOTEBOOK_ID', '1bfDjw5JGeqExdsUWYM41txvqlCGzOF99')
COLAB_CHECK_URL = f"https://colab.research.google.com/drive/{COLAB_NOTEBOOK_ID}"
CLOUDFLARE_TUNNEL_CHECK_INTERVAL = 10  # segundos
MAX_RETRIES = 30
K8S_NAMESPACE = "ai-film"
K8S_CONFIGMAP = "comfyui-config"


def check_colab_running() -> bool:
    """
    Verifica se o notebook do Colab está rodando
    """
    print("🔍 Verificando se Colab está rodando...")
    try:
        response = requests.get(COLAB_CHECK_URL, timeout=5)
        if response.status_code == 200:
            print("✅ Colab está acessível")
            return True
    except Exception as e:
        print(f"⚠️ Erro ao verificar Colab: {e}")
    return False


def get_cloudflare_url_from_file() -> Optional[str]:
    """
    Obtém URL do Cloudflare de arquivo compartilhado
    (Colab pode escrever em Google Drive)
    """
    print("📂 Buscando URL em arquivo compartilhado...")
    
    # Possíveis localizações
    possible_paths = [
        os.path.expanduser("~/Google Drive/comfyui_url.txt"),
        os.path.expanduser("~/gdrive/comfyui_url.txt"),
        "/tmp/comfyui_url.txt",
        "comfyui_url.txt"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    url = f.read().strip()
                    if url and url.startswith('https://'):
                        print(f"✅ URL encontrada: {url}")
                        return url
            except Exception as e:
                print(f"⚠️ Erro ao ler {path}: {e}")
    
    return None


def get_cloudflare_url_from_webhook() -> Optional[str]:
    """
    Obtém URL via webhook configurado no Colab
    
    No Colab, adicione este código:
    ```python
    import requests
    tunnel_url = "https://sua-url.trycloudflare.com"
    webhook_url = "https://seu-webhook.com/comfyui-url"
    requests.post(webhook_url, json={"url": tunnel_url})
    ```
    """
    print("🌐 Buscando URL via webhook...")
    
    webhook_url = os.getenv('COMFYUI_WEBHOOK_URL')
    if not webhook_url:
        print("⚠️ COMFYUI_WEBHOOK_URL não configurado")
        return None
    
    try:
        response = requests.get(webhook_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            url = data.get('url')
            if url:
                print(f"✅ URL obtida via webhook: {url}")
                return url
    except Exception as e:
        print(f"⚠️ Erro ao obter URL via webhook: {e}")
    
    return None


def get_cloudflare_url_from_env() -> Optional[str]:
    """
    Obtém URL de variável de ambiente (fallback)
    """
    url = os.getenv('COMFYUI_FALLBACK_URL')
    if url:
        print(f"✅ Usando URL de fallback: {url}")
        return url
    return None


def test_comfyui_connection(url: str) -> bool:
    """
    Testa se ComfyUI está acessível na URL
    """
    print(f"🧪 Testando conexão com ComfyUI: {url}")
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print("✅ ComfyUI está acessível!")
            return True
    except Exception as e:
        print(f"❌ ComfyUI não está acessível: {e}")
    return False


def update_kubernetes_configmap(url: str) -> bool:
    """
    Atualiza ConfigMap do Kubernetes com nova URL
    """
    print(f"🔄 Atualizando ConfigMap do Kubernetes...")
    
    try:
        # Criar ConfigMap YAML
        configmap_yaml = f"""
apiVersion: v1
kind: ConfigMap
metadata:
  name: {K8S_CONFIGMAP}
  namespace: {K8S_NAMESPACE}
data:
  COMFYUI_URL: "{url}"
  COMFYUI_UPDATED_AT: "{time.strftime('%Y-%m-%d %H:%M:%S')}"
"""
        
        # Salvar temporariamente
        temp_file = "/tmp/comfyui-configmap.yaml"
        with open(temp_file, 'w') as f:
            f.write(configmap_yaml)
        
        # Aplicar no Kubernetes
        result = subprocess.run(
            ['kubectl', 'apply', '-f', temp_file],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ ConfigMap atualizado com sucesso!")
            return True
        else:
            print(f"❌ Erro ao atualizar ConfigMap: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao atualizar ConfigMap: {e}")
        return False


def restart_comfyui_pods() -> bool:
    """
    Reinicia pods do ComfyUI para usar nova configuração
    """
    print("🔄 Reiniciando pods do ComfyUI...")
    
    try:
        # Rollout restart do deployment
        result = subprocess.run(
            ['kubectl', 'rollout', 'restart', 
             f'deployment/comfyui', '-n', K8S_NAMESPACE],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Pods reiniciados com sucesso!")
            
            # Aguardar rollout completar
            print("⏳ Aguardando rollout completar...")
            subprocess.run(
                ['kubectl', 'rollout', 'status', 
                 f'deployment/comfyui', '-n', K8S_NAMESPACE],
                check=True
            )
            print("✅ Rollout completo!")
            return True
        else:
            print(f"❌ Erro ao reiniciar pods: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao reiniciar pods: {e}")
        return False


def export_url_to_github_actions(url: str):
    """
    Exporta URL para GitHub Actions
    """
    github_output = os.getenv('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"comfyui_url={url}\n")
        print(f"✅ URL exportada para GitHub Actions")


def main():
    """
    Função principal
    """
    print("=" * 70)
    print("🎬 AI FILM PIPELINE - COLAB COMFYUI INTEGRATION")
    print("=" * 70)
    print()
    
    # 1. Verificar se Colab está rodando
    if not check_colab_running():
        print("\n⚠️ Colab não está rodando ou não está acessível")
        print("💡 Inicie o notebook manualmente:")
        print(f"   {COLAB_CHECK_URL}")
    
    # 2. Obter URL do Cloudflare (múltiplos métodos)
    comfyui_url = None
    
    # Método 1: Arquivo compartilhado
    comfyui_url = get_cloudflare_url_from_file()
    
    # Método 2: Webhook
    if not comfyui_url:
        comfyui_url = get_cloudflare_url_from_webhook()
    
    # Método 3: Variável de ambiente (fallback)
    if not comfyui_url:
        comfyui_url = get_cloudflare_url_from_env()
    
    if not comfyui_url:
        print("\n❌ ERRO: Não foi possível obter URL do ComfyUI")
        print("\n📋 INSTRUÇÕES:")
        print("1. Execute o notebook do Colab:")
        print(f"   {COLAB_CHECK_URL}")
        print("2. Copie a URL do túnel Cloudflare")
        print("3. Configure como secret:")
        print("   gh secret set COMFYUI_FALLBACK_URL -b 'https://sua-url.trycloudflare.com'")
        sys.exit(1)
    
    # 3. Testar conexão
    if not test_comfyui_connection(comfyui_url):
        print(f"\n❌ ComfyUI não está acessível em: {comfyui_url}")
        print("⏳ Aguardando ComfyUI ficar disponível...")
        
        for attempt in range(MAX_RETRIES):
            time.sleep(CLOUDFLARE_TUNNEL_CHECK_INTERVAL)
            if test_comfyui_connection(comfyui_url):
                break
            print(f"   Tentativa {attempt + 1}/{MAX_RETRIES}...")
        else:
            print(f"\n❌ Timeout: ComfyUI não ficou disponível após {MAX_RETRIES * CLOUDFLARE_TUNNEL_CHECK_INTERVAL}s")
            sys.exit(1)
    
    # 4. Atualizar Kubernetes (se disponível)
    try:
        # Verificar se kubectl está disponível
        subprocess.run(['kubectl', 'version', '--client'], 
                      capture_output=True, check=True)
        
        # Atualizar ConfigMap
        if update_kubernetes_configmap(comfyui_url):
            # Reiniciar pods
            restart_comfyui_pods()
        
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("\n⚠️ kubectl não disponível - pulando atualização do Kubernetes")
        print("💡 Para usar Kubernetes, instale kubectl:")
        print("   brew install kubectl  # macOS")
        print("   apt-get install kubectl  # Linux")
    
    # 5. Exportar para GitHub Actions
    export_url_to_github_actions(comfyui_url)
    
    # 6. Salvar em arquivo local
    config_file = "open3d_implementation/config/comfyui_config.json"
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    with open(config_file, 'w') as f:
        json.dump({
            "base_url": comfyui_url,
            "updated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
            "source": "colab_integration"
        }, f, indent=2)
    print(f"✅ Configuração salva em: {config_file}")
    
    print("\n" + "=" * 70)
    print("✅ INTEGRAÇÃO COMPLETA!")
    print("=" * 70)
    print(f"\n🎯 ComfyUI URL: {comfyui_url}")
    print(f"📊 Status: Operacional")
    print(f"🔄 Kubernetes: {'Atualizado' if 'kubectl' in str(subprocess.run(['which', 'kubectl'], capture_output=True)) else 'Não disponível'}")
    print()


if __name__ == "__main__":
    main()
