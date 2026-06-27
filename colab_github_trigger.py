"""
🚀 Colab GitHub Actions Trigger

ADICIONE ESTE CÓDIGO NO SEU NOTEBOOK COLAB!

Quando o ComfyUI estiver pronto, dispara automaticamente o GitHub Actions
para que você possa acompanhar o pipeline em tempo real.

INSTRUÇÕES:
1. Copie todo este código
2. Crie uma célula no seu notebook Colab (após ComfyUI iniciar)
3. Configure GITHUB_TOKEN e REPO
4. Execute a célula
5. GitHub Actions será disparado automaticamente!
"""

import requests
import json
import os
import time
from datetime import datetime


class ColabGitHubTrigger:
    """
    Dispara GitHub Actions automaticamente quando Colab está pronto
    """
    
    def __init__(self, github_token=None, repo=None):
        """
        Args:
            github_token: Token do GitHub (com scope workflow)
            repo: Nome do repo no formato "owner/repo" (ex: "Patricia7sp/AI_film")
        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.repo = repo or os.getenv("GITHUB_REPOSITORY", "Patricia7sp/AI_film")
        
        if not self.github_token:
            raise ValueError("❌ GITHUB_TOKEN não configurado!")
        
        if not self.repo:
            raise ValueError("❌ GITHUB_REPOSITORY não configurado!")
    
    def trigger_workflow(self, comfyui_url=None, gist_url=None):
        """
        Dispara GitHub Actions via repository_dispatch
        
        Args:
            comfyui_url: URL do ComfyUI (será enviada como payload)
            gist_url: URL do Gist (opcional)
        
        Returns:
            bool: True se sucesso, False caso contrário
        """
        print("=" * 70)
        print("🚀 DISPARANDO GITHUB ACTIONS")
        print("=" * 70)
        print(f"📦 Repositório: {self.repo}")
        print(f"🔗 ComfyUI URL: {comfyui_url or 'Será obtida do Gist'}")
        print("")
        
        # Preparar payload
        payload = {
            "event_type": "colab-ready",
            "client_payload": {
                "comfyui_url": comfyui_url,
                "gist_url": gist_url,
                "triggered_by": "colab",
                "timestamp": datetime.now().isoformat(),
                "status": "ready"
            }
        }
        
        # API endpoint
        url = f"https://api.github.com/repos/{self.repo}/dispatches"
        
        # Headers
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.github_token}",
            "Content-Type": "application/json"
        }
        
        try:
            print("📡 Enviando requisição para GitHub API...")
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            print(f"📊 Status Code: {response.status_code}")
            
            if response.status_code == 204:
                print("✅ GitHub Actions disparado com sucesso!")
                print("")
                print("🎯 O pipeline está executando agora!")
                print(f"👀 Acompanhe em: https://github.com/{self.repo}/actions")
                print("")
                print("=" * 70)
                return True
            
            else:
                print(f"❌ Falha ao disparar Actions: {response.status_code}")
                print(f"📄 Resposta: {response.text}")
                print("")
                print("💡 Verifique:")
                print("   - Token tem permissão 'workflow'")
                print("   - Repositório está correto")
                print("   - Workflow aceita 'repository_dispatch'")
                print("")
                return False
        
        except Exception as e:
            print(f"❌ Erro ao disparar Actions: {e}")
            print("")
            return False
    
    def trigger_with_retry(self, comfyui_url=None, max_retries=3):
        """
        Dispara Actions com retry automático
        """
        for attempt in range(max_retries):
            print(f"🔄 Tentativa {attempt + 1}/{max_retries}")
            
            if self.trigger_workflow(comfyui_url):
                return True
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Backoff exponencial
                print(f"⏳ Aguardando {wait_time}s antes de tentar novamente...")
                time.sleep(wait_time)
        
        print("❌ Todas as tentativas falharam!")
        return False


# ════════════════════════════════════════════════════════════════════════════
# FUNÇÃO DE USO SIMPLES
# ════════════════════════════════════════════════════════════════════════════

def notify_github_actions(comfyui_url=None, github_token=None, repo=None):
    """
    Função simples para disparar GitHub Actions
    
    Usage:
        notify_github_actions(comfyui_url="https://xxx.trycloudflare.com")
    """
    try:
        trigger = ColabGitHubTrigger(
            github_token=github_token,
            repo=repo
        )
        
        return trigger.trigger_with_retry(comfyui_url)
    
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


# ════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO E USO
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # CONFIGURE AQUI:
    
    # Opção 1: Definir diretamente (não recomendado - expõe token)
    # GITHUB_TOKEN = "ghp_seu_token_aqui"
    
    # Opção 2: Usar variável de ambiente (recomendado)
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    
    # Repositório no formato "owner/repo"
    REPO = "Patricia7sp/AI_film"
    
    # URL do ComfyUI (obter do Gist ou variável)
    COMFYUI_URL = os.getenv("COMFYUI_URL")  # ou colocar manualmente
    
    # Disparar Actions
    print("🎬 Iniciando disparo do GitHub Actions...")
    print("")
    
    success = notify_github_actions(
        comfyui_url=COMFYUI_URL,
        github_token=GITHUB_TOKEN,
        repo=REPO
    )
    
    if success:
        print("✅ Pipeline disparado com sucesso!")
        print("👀 Acompanhe os logs no GitHub Actions!")
    else:
        print("❌ Falha ao disparar pipeline")
        print("💡 Verifique configurações e tente novamente")


# ════════════════════════════════════════════════════════════════════════════
# INTEGRAÇÃO COM COMFYUI
# ════════════════════════════════════════════════════════════════════════════

"""
Para disparar automaticamente quando ComfyUI estiver pronto,
adicione este código após iniciar o ComfyUI:

# Aguardar ComfyUI ficar pronto
import time
import requests

def wait_comfyui_ready(url, max_wait=300):
    '''Aguarda ComfyUI ficar pronto'''
    print("⏳ Aguardando ComfyUI ficar pronto...")
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print("✅ ComfyUI está pronto!")
                return True
        except:
            pass
        
        time.sleep(5)
    
    print("❌ Timeout aguardando ComfyUI")
    return False

# URL do ComfyUI (obter da célula anterior ou Gist)
comfyui_url = "https://xxx.trycloudflare.com"

# Aguardar ficar pronto
if wait_comfyui_ready(comfyui_url):
    # Disparar GitHub Actions automaticamente
    notify_github_actions(
        comfyui_url=comfyui_url,
        github_token=os.getenv("GITHUB_TOKEN"),
        repo="Patricia7sp/AI_film"
    )
"""
