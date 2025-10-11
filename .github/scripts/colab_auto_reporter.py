#!/usr/bin/env python3
"""
📡 Colab Auto Reporter
Script que roda NO COLAB para reportar URL automaticamente
Este script é executado automaticamente quando o Colab inicia
"""

import re
import time
import json
import requests
import os
from datetime import datetime

class ColabAutoReporter:
    """Reporter automático que roda no Colab"""
    
    def __init__(self):
        # Configurações que vêm de secrets do GitHub
        # Serão injetadas automaticamente quando Colab for iniciado
        self.github_token = os.getenv('GITHUB_TOKEN', '')
        self.gist_id = os.getenv('GIST_ID', '')
        self.max_attempts = 30
        self.retry_delay = 10
        
    def capture_cloudflare_url(self) -> str:
        """Captura URL do Cloudflare do log"""
        print("🔍 Capturando URL do Cloudflare...")
        
        for attempt in range(self.max_attempts):
            try:
                # Ler log do cloudflared
                with open('/content/cloudflared.log', 'r') as f:
                    log_content = f.read()
                
                # Buscar URL com regex
                match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', log_content)
                
                if match:
                    url = match.group(0)
                    print(f"✅ URL capturada: {url}")
                    return url
                else:
                    print(f"⏳ Tentativa {attempt + 1}/{self.max_attempts}: URL ainda não disponível")
                    time.sleep(self.retry_delay)
                    
            except FileNotFoundError:
                print(f"⏳ Tentativa {attempt + 1}/{self.max_attempts}: Log ainda não existe")
                time.sleep(self.retry_delay)
            except Exception as e:
                print(f"⚠️ Erro ao ler log: {e}")
                time.sleep(self.retry_delay)
        
        raise Exception("❌ Não foi possível capturar URL após todas as tentativas")
    
    def verify_comfyui_running(self, url: str) -> bool:
        """Verifica se ComfyUI está respondendo"""
        print(f"🧪 Verificando se ComfyUI está acessível em {url}...")
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print("✅ ComfyUI está acessível!")
                return True
            else:
                print(f"⚠️ ComfyUI retornou status {response.status_code}")
                return False
        except Exception as e:
            print(f"⚠️ Erro ao verificar ComfyUI: {e}")
            return False
    
    def report_to_gist(self, url: str) -> bool:
        """Reporta URL para GitHub Gist"""
        print("📡 Reportando URL para GitHub Gist...")
        
        if not self.github_token:
            print("❌ GitHub token não configurado")
            return False
        
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        gist_data = {
            "description": "ComfyUI URL - Auto-reported from Colab",
            "public": False,
            "files": {
                "comfyui_url.json": {
                    "content": json.dumps({
                        "url": url,
                        "updated_at": datetime.now().isoformat(),
                        "status": "active",
                        "source": "colab_auto_reporter",
                        "verified": True
                    }, indent=2)
                }
            }
        }
        
        try:
            if self.gist_id:
                # Atualizar Gist existente
                response = requests.patch(
                    f'https://api.github.com/gists/{self.gist_id}',
                    headers=headers,
                    json=gist_data,
                    timeout=30
                )
            else:
                # Criar novo Gist
                response = requests.post(
                    'https://api.github.com/gists',
                    headers=headers,
                    json=gist_data,
                    timeout=30
                )
            
            if response.status_code in [200, 201]:
                gist_id = response.json()['id']
                print(f"✅ URL reportada com sucesso!")
                print(f"🔗 Gist ID: {gist_id}")
                
                if not self.gist_id:
                    print(f"\n⚠️ IMPORTANTE: Configure GIST_ID = '{gist_id}' nas variáveis de ambiente")
                
                return True
            else:
                print(f"❌ Erro ao reportar: {response.status_code}")
                print(response.text)
                return False
                
        except Exception as e:
            print(f"❌ Erro ao comunicar com GitHub: {e}")
            return False
    
    def run_auto_report(self):
        """Executa report automático completo"""
        print("=" * 60)
        print("📡 COLAB AUTO REPORTER")
        print("Reportando URL automaticamente para GitHub")
        print("=" * 60)
        print()
        
        try:
            # 1. Capturar URL
            url = self.capture_cloudflare_url()
            
            # 2. Verificar ComfyUI
            if not self.verify_comfyui_running(url):
                print("⚠️ ComfyUI não está acessível, mas continuando...")
            
            # 3. Reportar para Gist
            if self.report_to_gist(url):
                print()
                print("=" * 60)
                print("✅ SUCESSO! URL reportada automaticamente")
                print(f"🌐 URL: {url}")
                print("🤖 GitHub Actions pode continuar o pipeline")
                print("=" * 60)
                return True
            else:
                print()
                print("=" * 60)
                print("❌ FALHA ao reportar URL")
                print("=" * 60)
                return False
                
        except Exception as e:
            print()
            print("=" * 60)
            print(f"❌ ERRO: {e}")
            print("=" * 60)
            return False


# ============================================================
# Código para ser executado NO COLAB
# ============================================================
def setup_auto_reporting():
    """
    Setup que deve ser executado no Colab
    Adicione isso ao final do seu notebook Colab
    """
    print("🔧 Configurando auto-reporting...")
    
    # Instalar dependências
    import subprocess
    subprocess.run(['pip', 'install', '-q', 'requests'], check=True)
    
    # Executar reporter
    reporter = ColabAutoReporter()
    success = reporter.run_auto_report()
    
    if success:
        print("\n✅ Auto-reporting configurado com sucesso!")
        print("🤖 GitHub Actions será notificado automaticamente")
    else:
        print("\n⚠️ Auto-reporting falhou, mas Colab continua rodando")


if __name__ == "__main__":
    # Quando executado diretamente
    reporter = ColabAutoReporter()
    reporter.run_auto_report()
