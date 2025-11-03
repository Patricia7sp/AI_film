"""
🎬 COLAB MANAGER - VERSÃO SIMPLIFICADA (SEM FLASK)

FLUXO ALTERNATIVO:
  1. ComfyUI inicia
  2. URL publicada no Gist
  3. Você cola a história direto no código
  4. GitHub Actions disparado com história
  5. Pipeline executa
"""

import time, requests, json, os
from datetime import datetime
from IPython.display import display, HTML
from google.colab import userdata

# Config
GITHUB_TOKEN = userdata.get('GITHUB_TOKEN')
GITHUB_REPO = "Patricia7sp/AI_film"
COMFYUI_URL_GIST_ID = userdata.get('COMFYUI_URL_GIST_ID')
COMFYUI_URL = os.getenv("COMFYUI_URL")

# ═══════════════════════════════════════════════════════════════════
# 📝 INSIRA SUA HISTÓRIA AQUI:
# ═══════════════════════════════════════════════════════════════════

STORY = """
Em 2157, a humanidade descobriu portais para dimensões paralelas. 
Um cientista corajoso embarca em uma jornada para encontrar uma 
civilização perdida que pode salvar a Terra da extinção.
"""

# ═══════════════════════════════════════════════════════════════════

class SimpleColabManager:
    def __init__(self):
        self.github_token = GITHUB_TOKEN
        self.github_repo = GITHUB_REPO
        self.gist_id = COMFYUI_URL_GIST_ID
        self.comfyui_url = COMFYUI_URL
        self.story = STORY.strip()
    
    def update_gist(self):
        """Atualiza Gist com status"""
        if not self.gist_id or not self.github_token:
            return False
        
        try:
            status_data = {
                "comfyui_url": self.comfyui_url,
                "status": "ready",
                "timestamp": datetime.now().isoformat(),
                "story_length": len(self.story)
            }
            
            url = f"https://api.github.com/gists/{self.gist_id}"
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                gist_data = response.json()
                filename = list(gist_data['files'].keys())[0]
                
                files = {
                    filename: {
                        "content": json.dumps(status_data, indent=2)
                    }
                }
                
                response = requests.patch(url, headers=headers, json={"files": files})
                return response.status_code == 200
        except Exception as e:
            print(f"⚠️ Erro ao atualizar Gist: {e}")
            return False
    
    def trigger_github(self):
        """Dispara GitHub Actions com história"""
        print("=" * 70)
        print("🚀 DISPARANDO GITHUB ACTIONS")
        print("=" * 70)
        
        payload = {
            "event_type": "colab-ready",
            "client_payload": {
                "comfyui_url": self.comfyui_url,
                "story": self.story,
                "story_length": len(self.story),
                "timestamp": datetime.now().isoformat()
            }
        }
        
        url = f"https://api.github.com/repos/{self.github_repo}/dispatches"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            if res.status_code == 204:
                print(f"✅ GitHub Actions disparado!")
                print(f"📖 História: {len(self.story)} caracteres")
                print(f"👀 Acompanhe: https://github.com/{self.github_repo}/actions")
                print("=" * 70)
                return True
            else:
                print(f"❌ Erro: {res.status_code}")
                return False
        except Exception as e:
            print(f"❌ Erro: {e}")
            return False
    
    def display_ui(self):
        """Exibe interface visual"""
        html = f"""
        <div style="border: 3px solid #4CAF50; border-radius: 10px; padding: 20px;
                    background: linear-gradient(135deg, #f0f8ff 0%, #e6f7ff 100%);
                    font-family: Arial; margin: 10px 0;">
            <h2 style="color: #2196F3;">🎯 Colab Manager - Versão Simples</h2>
            
            <div style="background: white; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <strong>🔗 ComfyUI:</strong> {self.comfyui_url}<br>
                <strong>📖 História:</strong> {len(self.story)} caracteres<br>
                <strong>🚀 Status:</strong> <span style="color: #4CAF50;">PRONTO</span>
            </div>
            
            <div style="background: #fff3cd; padding: 10px; border-radius: 5px; border-left: 4px solid #ffc107;">
                <strong>💡 Próximos passos:</strong><br>
                1. ✅ História definida no código<br>
                2. ✅ GitHub Actions será disparado<br>
                3. 👀 Acompanhe no GitHub Actions<br>
                4. 🎬 Pipeline executará e gerará o filme
            </div>
        </div>
        """
        display(HTML(html))
    
    def start(self):
        print("=" * 70)
        print("🎯 COLAB MANAGER - VERSÃO SIMPLES")
        print("=" * 70)
        
        # Validações
        if not self.comfyui_url:
            print("❌ COMFYUI_URL não definida!")
            print("💡 Defina: os.environ['COMFYUI_URL'] = 'sua-url'")
            return
        
        if not self.story:
            print("❌ História não definida!")
            print("💡 Edite a variável STORY no código")
            return
        
        print(f"🔗 ComfyUI: {self.comfyui_url}")
        print(f"📖 História: {len(self.story)} caracteres")
        print("")
        
        # Atualizar Gist
        print("📝 Atualizando Gist...")
        self.update_gist()
        
        # Exibir UI
        self.display_ui()
        
        # Disparar GitHub Actions
        print("")
        self.trigger_github()
        
        print("")
        print("=" * 70)
        print("✅ SETUP COMPLETO!")
        print("=" * 70)
        print("")
        print("📋 O que acontece agora:")
        print("  1. GitHub Actions está executando")
        print("  2. Pipeline processará a história")
        print("  3. Imagens serão geradas")
        print("  4. Áudio será criado")
        print("  5. Vídeo final será compilado")
        print("")
        print(f"👀 Acompanhe: https://github.com/{self.github_repo}/actions")

# Executar
manager = SimpleColabManager()
manager.start()
