"""
🎬 COLAB MANAGER COM FLASK UI INTEGRADO

NOVO FLUXO:
  1. ComfyUI inicia
  2. URL publicada no Gist
  3. 🆕 FLASK UI ABRE (pop-up)
  4. Você insere história
  5. História salva
  6. 🆕 DEPOIS dispara GitHub Actions
  7. Pipeline executa
"""

import time, threading, requests, json, os, webbrowser
from datetime import datetime
from IPython.display import display, HTML, Javascript
from google.colab import userdata
from flask import Flask, request, jsonify, render_template_string
from flask_ngrok import run_with_ngrok

# Config
TIMEOUT_MINUTES = 30
GITHUB_TOKEN = userdata.get('GITHUB_TOKEN')
GITHUB_REPO = "Patricia7sp/AI_film"
COMFYUI_URL_GIST_ID = userdata.get('COMFYUI_URL_GIST_ID')
COMFYUI_URL = os.getenv("COMFYUI_URL")

# Flask App
app = Flask(__name__)
story_data = {"story": None, "submitted": False}

# Configurar ngrok (será iniciado manualmente)
flask_port = 5001  # Usar porta diferente para evitar conflito

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Film - Story Input</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
               min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { background: white; border-radius: 20px; max-width: 800px; padding: 40px; }
        h1 { color: #667eea; }
        textarea { width: 100%; min-height: 200px; padding: 15px; border: 2px solid #e0e0e0; 
                   border-radius: 10px; font-size: 16px; }
        button { padding: 15px 30px; border: none; border-radius: 10px; font-size: 1.1em; 
                 font-weight: 600; cursor: pointer; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                 color: white; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 AI Film - Insira sua História</h1>
        <form id="form">
            <textarea id="story" placeholder="Era uma vez..." required></textarea><br><br>
            <button type="submit">🚀 Enviar e Disparar Pipeline</button>
        </form>
        <div id="status"></div>
    </div>
    <script>
        document.getElementById('form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const story = document.getElementById('story').value;
            const res = await fetch('/submit', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({story})
            });
            const data = await res.json();
            document.getElementById('status').innerHTML = data.success ? 
                '✅ Enviado! GitHub Actions disparando...' : '❌ Erro';
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/submit', methods=['POST'])
def submit():
    story = request.get_json().get('story', '').strip()
    if story:
        story_data['story'] = story
        story_data['submitted'] = True
        print(f"\n✅ HISTÓRIA RECEBIDA! ({len(story)} chars)\n")
        return jsonify({'success': True})
    return jsonify({'success': False}), 400

# Manager Class
class ColabManager:
    def __init__(self):
        self.github_token = GITHUB_TOKEN
        self.github_repo = GITHUB_REPO
        self.gist_id = COMFYUI_URL_GIST_ID
        self.comfyui_url = COMFYUI_URL
        self.flask_url = None
        self.github_triggered = False
    
    def start_flask(self):
        """Inicia Flask com ngrok no Colab"""
        print("🌐 Iniciando Flask...")
        
        # Iniciar ngrok primeiro
        from pyngrok import ngrok
        
        try:
            # Matar processos anteriores
            ngrok.kill()
        except:
            pass
        
        # Iniciar túnel ngrok
        try:
            public_url = ngrok.connect(flask_port, bind_tls=True)
            self.flask_url = str(public_url)
            print(f"✅ ngrok túnel criado: {self.flask_url}")
        except Exception as e:
            print(f"❌ Erro ao criar túnel ngrok: {e}")
            return
        
        # Iniciar Flask em thread
        def run_flask():
            app.run(port=flask_port, use_reloader=False)
        
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        # Aguardar Flask iniciar
        time.sleep(3)
        print(f"✅ Flask rodando na porta {flask_port}")
    
    def open_flask_ui(self):
        if not self.flask_url:
            return
        display(HTML(f'''
        <div style="background: #4CAF50; color: white; padding: 20px; border-radius: 10px; text-align: center;">
            <h2>🎬 Insira sua História</h2>
            <a href="{self.flask_url}" target="_blank" 
               style="background: white; color: #4CAF50; padding: 15px 30px; text-decoration: none; 
                      border-radius: 5px; font-weight: bold; display: inline-block;">
                📝 ABRIR FLASK UI
            </a>
        </div>
        '''))
        display(Javascript(f'window.open("{self.flask_url}", "_blank");'))
    
    def wait_for_story(self, timeout_min=10):
        print(f"⏳ Aguardando história... (timeout: {timeout_min}min)")
        start = time.time()
        while time.time() - start < timeout_min * 60:
            if story_data['submitted']:
                print("✅ História recebida!")
                return story_data['story']
            time.sleep(2)
        print("⚠️ Timeout - sem história")
        return None
    
    def trigger_github(self, story=None):
        if self.github_triggered:
            return True
        print("🚀 Disparando GitHub Actions...")
        payload = {
            "event_type": "colab-ready",
            "client_payload": {
                "comfyui_url": self.comfyui_url,
                "story": story or "",
                "timestamp": datetime.now().isoformat()
            }
        }
        url = f"https://api.github.com/repos/{self.github_repo}/dispatches"
        headers = {"Authorization": f"token {self.github_token}", 
                   "Accept": "application/vnd.github.v3+json"}
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 204:
            print(f"✅ Disparado! https://github.com/{self.github_repo}/actions")
            self.github_triggered = True
            return True
        return False
    
    def start(self):
        print("=" * 70)
        print("🎯 INICIANDO COLAB MANAGER")
        print("=" * 70)
        
        # Verificar se ComfyUI URL está definida
        if not self.comfyui_url:
            print("⚠️ COMFYUI_URL não definida!")
            print("💡 Defina: os.environ['COMFYUI_URL'] = 'sua-url'")
            return
        
        print(f"🔗 ComfyUI: {self.comfyui_url}")
        print("")
        
        # Iniciar Flask
        try:
            self.start_flask()
        except Exception as e:
            print(f"❌ Erro ao iniciar Flask: {e}")
            print("💡 Tentando continuar sem Flask UI...")
            self.flask_url = None
        
        # Abrir UI se Flask iniciou
        if self.flask_url:
            self.open_flask_ui()
            story = self.wait_for_story(10)
        else:
            print("⚠️ Flask UI não disponível")
            print("💡 GitHub Actions será disparado sem história")
            story = None
        
        # Disparar GitHub Actions
        self.trigger_github(story)
        
        print("")
        print("=" * 70)
        print("✅ Setup completo!")
        print("=" * 70)

# Executar
manager = ColabManager()
manager.start()
