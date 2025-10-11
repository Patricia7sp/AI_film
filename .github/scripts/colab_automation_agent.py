#!/usr/bin/env python3
"""
🤖 Colab Automation Agent
Agente inteligente que gerencia Colab automaticamente via GitHub Actions
100% automação - zero intervenção manual
"""

import os
import sys
import time
import json
import requests
from datetime import datetime
from typing import Optional, Dict, Any

class ColabAutomationAgent:
    """Agente para automação completa do Colab"""
    
    def __init__(self):
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.colab_notebook_id = os.getenv('COLAB_NOTEBOOK_ID')
        self.gist_id = os.getenv('COMFYUI_URL_GIST_ID')
        self.max_retries = 30
        self.retry_delay = 10
        
    def log(self, message: str, level: str = "INFO"):
        """Log estruturado"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] [{level}] {message}")
        
    def trigger_colab_execution(self) -> bool:
        """
        Trigger Colab notebook execution via API
        Usa Google Colab API para iniciar notebook automaticamente
        """
        self.log("🚀 Iniciando execução do Colab notebook...")
        
        if not self.colab_notebook_id:
            self.log("⚠️ COLAB_NOTEBOOK_ID não configurado", "WARN")
            self.log("💡 Usando método alternativo: webhook trigger")
            return self._trigger_via_webhook()
        
        try:
            # Google Colab API endpoint
            url = f"https://colab.research.google.com/drive/{self.colab_notebook_id}"
            
            # Trigger execution via API
            # Nota: Requer autenticação OAuth2 configurada
            headers = {
                'Authorization': f'Bearer {self.github_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'action': 'execute_all',
                'runtime': 'gpu'
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                self.log("✅ Colab notebook iniciado com sucesso!")
                return True
            else:
                self.log(f"⚠️ Status {response.status_code}: {response.text}", "WARN")
                return self._trigger_via_webhook()
                
        except Exception as e:
            self.log(f"❌ Erro ao iniciar Colab: {e}", "ERROR")
            return self._trigger_via_webhook()
    
    def _trigger_via_webhook(self) -> bool:
        """
        Método alternativo: trigger via webhook
        Usa GitHub Actions para notificar sistema externo que inicia Colab
        """
        self.log("📡 Usando método webhook para iniciar Colab...")
        
        webhook_url = os.getenv('COLAB_TRIGGER_WEBHOOK')
        
        if not webhook_url:
            self.log("⚠️ Webhook não configurado. Assumindo Colab já rodando.", "WARN")
            return True
        
        try:
            payload = {
                'action': 'start_colab',
                'notebook_id': self.colab_notebook_id,
                'timestamp': datetime.now().isoformat(),
                'source': 'github_actions'
            }
            
            response = requests.post(webhook_url, json=payload, timeout=30)
            
            if response.status_code in [200, 201, 202]:
                self.log("✅ Webhook enviado com sucesso!")
                return True
            else:
                self.log(f"⚠️ Webhook retornou {response.status_code}", "WARN")
                return True  # Continue mesmo assim
                
        except Exception as e:
            self.log(f"⚠️ Erro no webhook: {e}", "WARN")
            return True  # Continue mesmo assim
    
    def wait_for_colab_ready(self) -> bool:
        """
        Aguarda Colab estar pronto e ComfyUI rodando
        Monitora Gist para detectar quando URL está disponível
        """
        self.log("⏳ Aguardando Colab iniciar e ComfyUI estar pronto...")
        
        for attempt in range(self.max_retries):
            self.log(f"🔍 Tentativa {attempt + 1}/{self.max_retries}")
            
            # Verificar se URL está no Gist
            url = self._get_url_from_gist()
            
            if url:
                self.log(f"✅ URL encontrada: {url}")
                
                # Verificar se ComfyUI está respondendo
                if self._verify_comfyui_accessible(url):
                    self.log("✅ ComfyUI está acessível e pronto!")
                    return True
                else:
                    self.log("⏳ URL encontrada mas ComfyUI ainda não está pronto...")
            else:
                self.log("⏳ URL ainda não disponível no Gist...")
            
            time.sleep(self.retry_delay)
        
        self.log("❌ Timeout aguardando Colab ficar pronto", "ERROR")
        return False
    
    def _get_url_from_gist(self) -> Optional[str]:
        """Busca URL do ComfyUI no Gist"""
        if not self.gist_id:
            return None
        
        try:
            url = f"https://api.github.com/gists/{self.gist_id}"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                gist_data = response.json()
                
                # Buscar arquivo comfyui_url.json
                files = gist_data.get('files', {})
                url_file = files.get('comfyui_url.json', {})
                content = url_file.get('content', '{}')
                
                data = json.loads(content)
                comfyui_url = data.get('url')
                
                if comfyui_url:
                    return comfyui_url
            
            return None
            
        except Exception as e:
            self.log(f"⚠️ Erro ao buscar Gist: {e}", "WARN")
            return None
    
    def _verify_comfyui_accessible(self, url: str) -> bool:
        """Verifica se ComfyUI está acessível"""
        try:
            response = requests.get(url, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def capture_and_export_url(self) -> Optional[str]:
        """
        Captura URL do Colab e exporta para GitHub Actions
        Retorna URL para ser usada nos próximos jobs
        """
        self.log("📡 Capturando URL do ComfyUI...")
        
        url = self._get_url_from_gist()
        
        if not url:
            self.log("❌ Não foi possível capturar URL", "ERROR")
            return None
        
        self.log(f"✅ URL capturada: {url}")
        
        # Exportar para GitHub Actions output
        github_output = os.getenv('GITHUB_OUTPUT')
        if github_output:
            with open(github_output, 'a') as f:
                f.write(f"comfyui_url={url}\n")
            self.log("✅ URL exportada para GitHub Actions")
        
        # Também exportar como variável de ambiente
        print(f"::set-output name=comfyui_url::{url}")
        
        return url
    
    def monitor_colab_health(self, url: str) -> Dict[str, Any]:
        """
        Monitora saúde do Colab e ComfyUI
        Retorna métricas para decisões inteligentes
        """
        self.log("🏥 Monitorando saúde do sistema...")
        
        health = {
            'status': 'unknown',
            'accessible': False,
            'response_time': None,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            response_time = time.time() - start_time
            
            health['accessible'] = response.status_code == 200
            health['response_time'] = round(response_time, 2)
            health['status'] = 'healthy' if health['accessible'] else 'unhealthy'
            
            self.log(f"✅ Status: {health['status']} (tempo: {health['response_time']}s)")
            
        except Exception as e:
            health['status'] = 'error'
            health['error'] = str(e)
            self.log(f"❌ Erro no health check: {e}", "ERROR")
        
        return health
    
    def run_full_automation(self) -> bool:
        """
        Executa automação completa:
        1. Inicia Colab
        2. Aguarda estar pronto
        3. Captura URL
        4. Verifica saúde
        5. Exporta para pipeline
        """
        self.log("🤖 Iniciando automação completa do Colab...")
        self.log("=" * 60)
        
        # Passo 1: Iniciar Colab
        if not self.trigger_colab_execution():
            self.log("❌ Falha ao iniciar Colab", "ERROR")
            return False
        
        # Passo 2: Aguardar estar pronto
        if not self.wait_for_colab_ready():
            self.log("❌ Colab não ficou pronto no tempo esperado", "ERROR")
            return False
        
        # Passo 3: Capturar URL
        url = self.capture_and_export_url()
        if not url:
            self.log("❌ Falha ao capturar URL", "ERROR")
            return False
        
        # Passo 4: Verificar saúde
        health = self.monitor_colab_health(url)
        if health['status'] != 'healthy':
            self.log("⚠️ Sistema não está saudável", "WARN")
            return False
        
        self.log("=" * 60)
        self.log("✅ Automação completa executada com sucesso!")
        self.log(f"🌐 ComfyUI URL: {url}")
        self.log(f"🏥 Status: {health['status']}")
        self.log(f"⏱️ Tempo de resposta: {health['response_time']}s")
        
        return True


def main():
    """Ponto de entrada principal"""
    agent = ColabAutomationAgent()
    
    print("=" * 60)
    print("🤖 COLAB AUTOMATION AGENT")
    print("100% Automação - Zero Intervenção Manual")
    print("=" * 60)
    print()
    
    success = agent.run_full_automation()
    
    if success:
        print()
        print("✅ SUCESSO! Pipeline pode continuar.")
        sys.exit(0)
    else:
        print()
        print("❌ FALHA! Verifique os logs acima.")
        sys.exit(1)


if __name__ == "__main__":
    main()
