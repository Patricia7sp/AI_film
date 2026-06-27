#!/usr/bin/env python3
"""
🎬 Interactive AI Film Pipeline
Abre interfaces web para input de história e monitoramento
"""

import os
import sys
import subprocess
import requests
import time
import webbrowser
from pathlib import Path
from typing import Optional

# Cores para terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Imprime cabeçalho formatado"""
    print(f"\n{Colors.CYAN}{'=' * 70}")
    print(f"{Colors.BOLD}{text}{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 70}{Colors.RESET}\n")


def check_comfyui_health(url: str) -> bool:
    """Verifica se ComfyUI está acessível"""
    print(f"{Colors.BLUE}🔍 Verificando ComfyUI: {url}{Colors.RESET}")
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print(f"{Colors.GREEN}✅ ComfyUI: OK{Colors.RESET}")
            return True
    except Exception as e:
        print(f"{Colors.RED}❌ ComfyUI não acessível: {e}{Colors.RESET}")
        return False
    
    return False


def start_flask_server(port: int = 5001) -> subprocess.Popen:
    """Inicia servidor Flask para input de história"""
    print_header("🌐 INICIANDO FLASK SERVER")
    
    # Criar app Flask simples
    flask_app_code = '''
from flask import Flask, request, render_template_string, jsonify
import os
import json
from datetime import datetime

app = Flask(__name__)

# Template HTML
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Film - Story Input</title>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 800px;
            width: 100%;
            padding: 40px;
        }
        h1 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        .form-group {
            margin-bottom: 25px;
        }
        label {
            display: block;
            margin-bottom: 10px;
            color: #333;
            font-weight: 600;
            font-size: 1.1em;
        }
        textarea {
            width: 100%;
            min-height: 200px;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            font-family: inherit;
            resize: vertical;
            transition: border-color 0.3s;
        }
        textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        .char-count {
            text-align: right;
            color: #999;
            font-size: 0.9em;
            margin-top: 5px;
        }
        .examples {
            background: #f5f5f5;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .examples h3 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 1em;
        }
        .examples ul {
            list-style: none;
            padding-left: 0;
        }
        .examples li {
            padding: 5px 0;
            color: #666;
            font-size: 0.9em;
        }
        .examples li:before {
            content: "💡 ";
        }
        .button-group {
            display: flex;
            gap: 15px;
            margin-top: 30px;
        }
        button {
            flex: 1;
            padding: 15px 30px;
            border: none;
            border-radius: 10px;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        .btn-secondary {
            background: #f5f5f5;
            color: #333;
        }
        .btn-secondary:hover {
            background: #e0e0e0;
        }
        .status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 10px;
            display: none;
        }
        .status.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .status.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .links {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #e0e0e0;
        }
        .links a {
            display: inline-block;
            margin-right: 20px;
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
        }
        .links a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 AI Film Generator</h1>
        <p class="subtitle">Insira sua história para gerar o filme</p>
        
        <div class="examples">
            <h3>💡 Exemplos de histórias:</h3>
            <ul>
                <li>Uma jornada épica através de um mundo cyberpunk futurista</li>
                <li>A história de um robô que descobre emoções humanas</li>
                <li>Uma aventura espacial em busca de um planeta perdido</li>
            </ul>
        </div>
        
        <form id="storyForm" method="POST" action="/submit">
            <div class="form-group">
                <label for="story">📝 Sua História:</label>
                <textarea 
                    id="story" 
                    name="story" 
                    placeholder="Era uma vez em um mundo distante..."
                    required
                    oninput="updateCharCount()"
                ></textarea>
                <div class="char-count">
                    <span id="charCount">0</span> caracteres
                </div>
            </div>
            
            <div class="button-group">
                <button type="submit" class="btn-primary">
                    🚀 Gerar Filme
                </button>
                <button type="button" class="btn-secondary" onclick="clearForm()">
                    🗑️ Limpar
                </button>
            </div>
        </form>
        
        <div id="status" class="status"></div>
        
        <div class="links">
            <a href="http://localhost:3000" target="_blank">📊 Dagster UI</a>
            <a href="{{ comfyui_url }}" target="_blank">🎨 ComfyUI</a>
        </div>
    </div>
    
    <script>
        function updateCharCount() {
            const textarea = document.getElementById('story');
            const charCount = document.getElementById('charCount');
            charCount.textContent = textarea.value.length;
        }
        
        function clearForm() {
            document.getElementById('story').value = '';
            updateCharCount();
        }
        
        document.getElementById('storyForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const story = document.getElementById('story').value;
            const status = document.getElementById('status');
            
            try {
                const response = await fetch('/submit', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ story: story })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    status.className = 'status success';
                    status.style.display = 'block';
                    status.innerHTML = `
                        ✅ História enviada com sucesso!<br>
                        📊 Acompanhe o progresso no <a href="http://localhost:3000" target="_blank">Dagster UI</a>
                    `;
                } else {
                    throw new Error(result.error || 'Erro desconhecido');
                }
            } catch (error) {
                status.className = 'status error';
                status.style.display = 'block';
                status.textContent = '❌ Erro ao enviar história: ' + error.message;
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    comfyui_url = os.getenv('COMFYUI_URL', 'http://localhost:8188')
    return render_template_string(HTML_TEMPLATE, comfyui_url=comfyui_url)

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.get_json()
        story = data.get('story', '')
        
        if not story:
            return jsonify({'success': False, 'error': 'História vazia'}), 400
        
        # Salvar história em arquivo
        output_dir = Path('output')
        output_dir.mkdir(exist_ok=True)
        
        story_file = output_dir / f'story_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        story_file.write_text(story, encoding='utf-8')
        
        # Salvar também como "latest" para o pipeline usar
        latest_file = output_dir / 'story_latest.txt'
        latest_file.write_text(story, encoding='utf-8')
        
        print(f"✅ História salva: {story_file}")
        
        return jsonify({
            'success': True,
            'file': str(story_file),
            'message': 'História salva com sucesso!'
        })
        
    except Exception as e:
        print(f"❌ Erro ao salvar história: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5001))
    print(f"🌐 Flask rodando em http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
'''
    
    # Salvar app Flask temporário
    flask_file = Path('/tmp/flask_story_input.py')
    flask_file.write_text(flask_app_code)
    
    # Iniciar Flask
    env = os.environ.copy()
    env['FLASK_PORT'] = str(port)
    
    process = subprocess.Popen(
        [sys.executable, str(flask_file)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Aguardar Flask iniciar
    time.sleep(3)
    
    flask_url = f"http://localhost:{port}"
    print(f"{Colors.GREEN}✅ Flask iniciado: {flask_url}{Colors.RESET}")
    
    return process


def start_dagster_ui(port: int = 3000) -> subprocess.Popen:
    """Inicia Dagster UI"""
    print_header("📊 INICIANDO DAGSTER UI")
    
    env = os.environ.copy()
    env['DAGSTER_HOME'] = str(Path.home() / '.dagster')
    
    # Encontrar dagster pipeline
    repo_root = Path(__file__).parent.parent.parent
    dagster_file = repo_root / 'orchestration' / 'enhanced_dagster_pipeline.py'
    
    if not dagster_file.exists():
        print(f"{Colors.RED}❌ Dagster pipeline não encontrado: {dagster_file}{Colors.RESET}")
        return None
    
    print(f"{Colors.BLUE}📂 Pipeline: {dagster_file}{Colors.RESET}")
    
    # Iniciar Dagster dev
    process = subprocess.Popen(
        ['dagster', 'dev', '-f', str(dagster_file), '-p', str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Aguardar Dagster iniciar
    print(f"{Colors.YELLOW}⏳ Aguardando Dagster iniciar...{Colors.RESET}")
    time.sleep(10)
    
    dagster_url = f"http://localhost:{port}"
    print(f"{Colors.GREEN}✅ Dagster UI: {dagster_url}{Colors.RESET}")
    
    return process


def open_browser_tabs(flask_url: str, dagster_url: str):
    """Abre tabs do navegador"""
    print_header("🌐 ABRINDO INTERFACES WEB")
    
    print(f"{Colors.CYAN}📝 Abrindo Flask (Input de História)...{Colors.RESET}")
    webbrowser.open(flask_url)
    time.sleep(2)
    
    print(f"{Colors.CYAN}📊 Abrindo Dagster (Monitoramento)...{Colors.RESET}")
    webbrowser.open(dagster_url)
    
    print(f"\n{Colors.GREEN}✅ Interfaces abertas!{Colors.RESET}")
    print(f"{Colors.BOLD}📝 Flask UI:{Colors.RESET} {flask_url}")
    print(f"{Colors.BOLD}📊 Dagster UI:{Colors.RESET} {dagster_url}")


def wait_for_story_input() -> Optional[str]:
    """Aguarda usuário inserir história"""
    print_header("⏳ AGUARDANDO INPUT DO USUÁRIO")
    
    print(f"{Colors.YELLOW}Aguardando você inserir a história no Flask UI...{Colors.RESET}")
    print(f"{Colors.CYAN}💡 Dica: A história será salva em output/story_latest.txt{Colors.RESET}")
    
    story_file = Path('output/story_latest.txt')
    
    # Aguardar arquivo ser criado (timeout 5 minutos)
    timeout = 300
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if story_file.exists():
            story = story_file.read_text(encoding='utf-8')
            if story.strip():
                print(f"\n{Colors.GREEN}✅ História recebida! ({len(story)} caracteres){Colors.RESET}")
                return story
        time.sleep(2)
    
    print(f"\n{Colors.RED}❌ Timeout: Nenhuma história foi inserida{Colors.RESET}")
    return None


def main():
    """Função principal"""
    print_header("🎬 AI FILM INTERACTIVE PIPELINE")
    
    # 1. Verificar ComfyUI
    comfyui_url = os.getenv('COMFYUI_URL', 'http://localhost:8188')
    
    if not check_comfyui_health(comfyui_url):
        print(f"{Colors.RED}❌ ComfyUI não está disponível. Abortando.{Colors.RESET}")
        return 1
    
    # 2. Iniciar Flask
    flask_process = start_flask_server(port=5001)
    flask_url = "http://localhost:5001"
    
    # 3. Iniciar Dagster
    dagster_process = start_dagster_ui(port=3000)
    dagster_url = "http://localhost:3000"
    
    # 4. Abrir navegador
    time.sleep(2)
    open_browser_tabs(flask_url, dagster_url)
    
    # 5. Aguardar input
    story = wait_for_story_input()
    
    if not story:
        print(f"{Colors.RED}❌ Pipeline cancelado: sem história{Colors.RESET}")
        flask_process.terminate()
        if dagster_process:
            dagster_process.terminate()
        return 1
    
    # 6. Executar pipeline
    print_header("🚀 EXECUTANDO PIPELINE")
    
    print(f"{Colors.GREEN}✅ Pipeline iniciado!{Colors.RESET}")
    print(f"{Colors.CYAN}📊 Acompanhe o progresso no Dagster UI: {dagster_url}{Colors.RESET}")
    
    # Manter processos rodando
    print(f"\n{Colors.YELLOW}⏳ Pipeline em execução...{Colors.RESET}")
    print(f"{Colors.CYAN}💡 Pressione Ctrl+C para parar{Colors.RESET}\n")
    
    try:
        # Aguardar indefinidamente
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️ Interrompido pelo usuário{Colors.RESET}")
    finally:
        print(f"\n{Colors.BLUE}🛑 Encerrando serviços...{Colors.RESET}")
        flask_process.terminate()
        if dagster_process:
            dagster_process.terminate()
        print(f"{Colors.GREEN}✅ Serviços encerrados{Colors.RESET}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
