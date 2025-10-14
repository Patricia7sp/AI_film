"""
🎯 SETUP COMPLETO PARA COLAB - TUDO EM UM!

Este arquivo combina:
  ✅ Monitor de inatividade (auto-shutdown)
  ✅ Trigger automático do GitHub Actions
  ✅ Atualização do Gist
  ✅ Status em tempo real

INSTRUÇÕES:
1. Copie TODO este código
2. Crie uma célula no início do seu notebook Colab (após imports)
3. Configure as variáveis abaixo
4. Execute a célula ▶️
5. Pronto! Tudo automatizado!

FLUXO:
  Você abre Colab (1 clique)
    ↓
  Notebook executa automaticamente
    ↓
  ComfyUI inicia
    ↓
  Este código:
    - Publica URL no Gist
    - Dispara GitHub Actions automaticamente
    - Monitora inatividade
    - Auto-shutdown após timeout
"""

import time
import threading
import requests
import json
import os
from datetime import datetime, timedelta
from IPython.display import display, HTML


# ════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO - AJUSTE AQUI!
# ════════════════════════════════════════════════════════════════════════════

# Timeouts e configurações
TIMEOUT_MINUTES = 30  # Auto-shutdown após X minutos de inatividade
                      # 30 = muito econômico
                      # 60 = balanceado
                      # 90 = mais flexível

# GitHub configurações
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Token com scope 'workflow'
GITHUB_REPO = "Patricia7sp/AI_film"       # Seu repositório

# Gist configurações
GIST_ID = os.getenv("COMFYUI_URL_GIST_ID")  # ID do seu Gist

# ComfyUI URL (será obtida automaticamente ou você pode definir)
COMFYUI_URL = os.getenv("COMFYUI_URL")  # ou definir manualmente após obter


# ════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPAL - GERENCIA TUDO
# ════════════════════════════════════════════════════════════════════════════

class ColabCompleteManager:
    """
    Gerenciador completo do Colab:
    - Monitor de inatividade
    - Trigger do GitHub Actions
    - Atualização do Gist
    - Status em tempo real
    """
    
    def __init__(self, timeout_minutes=30, github_token=None, github_repo=None, 
                 gist_id=None, comfyui_url=None):
        # Configurações
        self.timeout = timeout_minutes * 60
        self.timeout_minutes = timeout_minutes
        self.github_token = github_token
        self.github_repo = github_repo
        self.gist_id = gist_id
        self.comfyui_url = comfyui_url
        
        # Estado
        self.last_activity = time.time()
        self.start_time = time.time()
        self.running = True
        self.total_requests = 0
        self.status = "starting"
        self.github_triggered = False
        
    # ────────────────────────────────────────────────────────────────────────
    # GIST - ATUALIZAÇÃO DE STATUS
    # ────────────────────────────────────────────────────────────────────────
    
    def update_gist(self, status=None):
        """Atualiza Gist com status atual"""
        if not self.gist_id or not self.github_token:
            return False
        
        try:
            status_data = {
                "comfyui_url": self.comfyui_url,
                "status": status or self.status,
                "last_activity": datetime.now().isoformat(),
                "uptime_minutes": int(self.get_uptime()),
                "inactive_minutes": int(self.get_inactive_time()),
                "auto_shutdown_in_minutes": int(self.get_time_until_shutdown()),
                "total_requests": self.total_requests,
                "timeout_minutes": self.timeout_minutes,
                "github_actions_triggered": self.github_triggered
            }
            
            url = f"https://api.github.com/gists/{self.gist_id}"
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            # Obter conteúdo atual
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                gist_data = response.json()
                filename = list(gist_data['files'].keys())[0]
                
                # Atualizar
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
    
    # ────────────────────────────────────────────────────────────────────────
    # GITHUB ACTIONS - TRIGGER AUTOMÁTICO
    # ────────────────────────────────────────────────────────────────────────
    
    def trigger_github_actions(self):
        """Dispara GitHub Actions automaticamente"""
        if not self.github_token or not self.github_repo:
            print("⚠️ GitHub não configurado, pulando trigger")
            return False
        
        if self.github_triggered:
            print("✅ GitHub Actions já foi disparado anteriormente")
            return True
        
        print("=" * 70)
        print("🚀 DISPARANDO GITHUB ACTIONS")
        print("=" * 70)
        
        payload = {
            "event_type": "colab-ready",
            "client_payload": {
                "comfyui_url": self.comfyui_url,
                "triggered_by": "colab",
                "timestamp": datetime.now().isoformat(),
                "status": "ready"
            }
        }
        
        url = f"https://api.github.com/repos/{self.github_repo}/dispatches"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.github_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if response.status_code == 204:
                print("✅ GitHub Actions disparado com sucesso!")
                print(f"👀 Acompanhe em: https://github.com/{self.github_repo}/actions")
                print("=" * 70)
                self.github_triggered = True
                self.update_gist("active")
                return True
            else:
                print(f"❌ Falha: {response.status_code}")
                return False
        
        except Exception as e:
            print(f"❌ Erro ao disparar: {e}")
            return False
    
    # ────────────────────────────────────────────────────────────────────────
    # MONITOR DE INATIVIDADE
    # ────────────────────────────────────────────────────────────────────────
    
    def get_inactive_time(self):
        """Tempo de inatividade em minutos"""
        return (time.time() - self.last_activity) / 60
    
    def get_uptime(self):
        """Tempo total ativo em minutos"""
        return (time.time() - self.start_time) / 60
    
    def get_time_until_shutdown(self):
        """Tempo restante até shutdown em minutos"""
        return max(0, self.timeout_minutes - self.get_inactive_time())
    
    def update_activity(self):
        """Atualiza timestamp de atividade"""
        self.last_activity = time.time()
        self.total_requests += 1
        self.status = "active"
        print(f"✅ Atividade! Timer resetado (Req #{self.total_requests})")
    
    def monitor_inactivity(self):
        """Loop de monitoramento (roda em thread)"""
        print(f"🔍 Monitor iniciado - checando a cada 1 minuto")
        print(f"⏱️ Auto-shutdown: {self.timeout_minutes} min de inatividade")
        print("")
        
        while self.running:
            time.sleep(60)
            
            inactive_min = self.get_inactive_time()
            time_remaining = self.timeout_minutes - inactive_min
            
            # Atualizar Gist a cada 5 minutos
            if int(inactive_min) % 5 == 0:
                self.update_gist()
            
            # Avisos progressivos
            if time_remaining <= 5 and time_remaining > 4:
                self.status = "idle"
                print(f"⚠️ ATENÇÃO: Auto-shutdown em 5 minutos!")
                self.update_gist("idle")
            
            elif time_remaining <= 2 and time_remaining > 1:
                print(f"⚠️ Auto-shutdown em 2 minutos!")
            
            elif time_remaining <= 1 and time_remaining > 0:
                print(f"⚠️ ÚLTIMA CHANCE: 1 minuto!")
            
            # Shutdown
            if inactive_min >= self.timeout_minutes:
                print("=" * 70)
                print(f"💤 INATIVO por {inactive_min:.1f} minutos")
                print(f"💰 Economizando compute units...")
                print(f"📊 Sessão: {self.get_uptime():.1f}min total, {self.total_requests} requisições")
                print("=" * 70)
                print("🔌 Desconectando em 10 segundos...")
                
                self.update_gist("offline")
                time.sleep(10)
                
                try:
                    from google.colab import runtime
                    runtime.unassign()
                except Exception as e:
                    print(f"❌ Erro ao desconectar: {e}")
                
                break
    
    # ────────────────────────────────────────────────────────────────────────
    # INICIALIZAÇÃO
    # ────────────────────────────────────────────────────────────────────────
    
    def start(self, auto_trigger_github=True):
        """Inicia todos os sistemas"""
        print("=" * 70)
        print("🎯 COLAB COMPLETE MANAGER - INICIANDO")
        print("=" * 70)
        print(f"⏱️ Timeout: {self.timeout_minutes} minutos")
        print(f"🔗 ComfyUI: {self.comfyui_url or 'Aguardando...'}")
        print(f"🐙 GitHub: {self.github_repo if self.github_repo else 'Não configurado'}")
        print(f"📝 Gist: {self.gist_id if self.gist_id else 'Não configurado'}")
        print("=" * 70)
        print("")
        
        # Atualizar Gist inicial
        if self.comfyui_url:
            self.status = "ready"
            self.update_gist("ready")
            
            # Disparar GitHub Actions automaticamente
            if auto_trigger_github:
                time.sleep(2)  # Pequeno delay para estabilizar
                self.trigger_github_actions()
        
        # Iniciar monitor em thread
        thread = threading.Thread(target=self.monitor_inactivity)
        thread.daemon = True
        thread.start()
        
        # UI
        self.display_ui()
        
        print("✅ Todos os sistemas iniciados!")
        print("")
    
    def display_ui(self):
        """Interface visual"""
        html = f"""
        <div style="border: 3px solid #4CAF50; border-radius: 10px; padding: 20px; 
                    background: linear-gradient(135deg, #f0f8ff 0%, #e6f7ff 100%); 
                    font-family: 'Segoe UI', Tahoma, sans-serif; margin: 10px 0;">
            <h2 style="margin: 0 0 15px 0; color: #2196F3; display: flex; align-items: center;">
                🎯 <span style="margin-left: 10px;">Colab Manager Ativo</span>
            </h2>
            
            <div style="background: white; padding: 15px; border-radius: 5px; margin-bottom: 10px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div>
                        <strong>⏱️ Timeout:</strong> {self.timeout_minutes} minutos<br>
                        <strong>🔗 ComfyUI:</strong> {'✅ Configurado' if self.comfyui_url else '⏳ Aguardando'}<br>
                        <strong>📝 Gist:</strong> {'✅ Ativo' if self.gist_id else '❌ Não configurado'}
                    </div>
                    <div>
                        <strong>🐙 GitHub Actions:</strong> {'✅ Configurado' if self.github_repo else '❌ Não configurado'}<br>
                        <strong>📊 Status:</strong> <span style="color: #4CAF50; font-weight: bold;">{self.status.upper()}</span><br>
                        <strong>🚀 Auto-trigger:</strong> {'✅ Habilitado' if self.github_repo else '❌ Desabilitado'}
                    </div>
                </div>
            </div>
            
            <div style="background: #fff3cd; padding: 10px; border-radius: 5px; border-left: 4px solid #ffc107;">
                <strong>💡 Como funciona:</strong><br>
                • Sistema monitora inatividade automaticamente<br>
                • A cada requisição, timer reseta<br>
                • Após {self.timeout_minutes}min sem uso → auto-shutdown<br>
                • GitHub Actions disparado automaticamente quando pronto<br>
                • Acompanhe pipeline em tempo real no GitHub!
            </div>
        </div>
        """
        display(HTML(html))


# ════════════════════════════════════════════════════════════════════════════
# INICIALIZAÇÃO AUTOMÁTICA
# ════════════════════════════════════════════════════════════════════════════

# Criar gerenciador
manager = ColabCompleteManager(
    timeout_minutes=TIMEOUT_MINUTES,
    github_token=GITHUB_TOKEN,
    github_repo=GITHUB_REPO,
    gist_id=GIST_ID,
    comfyui_url=COMFYUI_URL
)

# Iniciar sistemas
manager.start(auto_trigger_github=True)

print("🎉 Setup completo! Tudo está automatizado!")
print("")
print("📋 O que acontece agora:")
print("  1. Sistema monitora inatividade")
print(f"  2. Auto-shutdown após {TIMEOUT_MINUTES}min sem uso")
print("  3. GitHub Actions será disparado automaticamente")
print("  4. Você acompanha tudo no GitHub!")
print("")
print(f"👀 Acompanhe: https://github.com/{GITHUB_REPO}/actions")
print("")


# ════════════════════════════════════════════════════════════════════════════
# FUNÇÕES DE CONVENIÊNCIA
# ════════════════════════════════════════════════════════════════════════════

def set_comfyui_url(url):
    """Define URL do ComfyUI e dispara GitHub Actions"""
    manager.comfyui_url = url
    manager.update_gist("ready")
    manager.trigger_github_actions()
    print(f"✅ ComfyUI URL configurada: {url}")
    print("🚀 GitHub Actions disparado!")


def keep_alive():
    """Mantém sistema ativo (reseta timer)"""
    manager.update_activity()


def force_shutdown():
    """Força shutdown imediato"""
    manager.running = False
    print("🔌 Shutdown forçado!")


# Exportar manager para uso global
__manager = manager
