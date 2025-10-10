#!/usr/bin/env python3
"""
Webhook Handler para receber notificações do Google Colab
quando ComfyUI estiver pronto

Este script pode rodar como:
1. Servidor Flask local (para desenvolvimento)
2. GitHub Actions workflow trigger (para CI/CD)
3. Kubernetes Job (para produção)
"""

import os
import json
import time
from datetime import datetime
from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)

# Armazenamento em memória (para desenvolvimento)
# Em produção, use Redis ou banco de dados
comfyui_status = {
    "url": None,
    "last_updated": None,
    "status": "waiting",
    "colab_session_id": None
}


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "colab-webhook-handler",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/comfyui-url', methods=['POST'])
def receive_comfyui_url():
    """
    Recebe URL do ComfyUI do Colab
    
    Payload esperado:
    {
        "url": "https://xxx.trycloudflare.com",
        "colab_session_id": "optional-session-id",
        "gpu_type": "T4",
        "status": "ready"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                "error": "Missing 'url' in payload"
            }), 400
        
        url = data['url']
        
        # Validar URL
        if not url.startswith('https://'):
            return jsonify({
                "error": "URL must start with https://"
            }), 400
        
        # Atualizar status
        comfyui_status.update({
            "url": url,
            "last_updated": datetime.now().isoformat(),
            "status": "ready",
            "colab_session_id": data.get('colab_session_id'),
            "gpu_type": data.get('gpu_type', 'unknown')
        })
        
        print(f"✅ ComfyUI URL recebida: {url}")
        print(f"📊 Status: {json.dumps(comfyui_status, indent=2)}")
        
        # Atualizar Kubernetes ConfigMap (se disponível)
        try:
            update_kubernetes_config(url)
        except Exception as e:
            print(f"⚠️ Não foi possível atualizar Kubernetes: {e}")
        
        # Salvar em arquivo para GitHub Actions
        save_url_to_file(url)
        
        return jsonify({
            "status": "success",
            "message": "ComfyUI URL received and processed",
            "url": url,
            "timestamp": comfyui_status['last_updated']
        }), 200
        
    except Exception as e:
        print(f"❌ Erro ao processar webhook: {e}")
        return jsonify({
            "error": str(e)
        }), 500


@app.route('/comfyui-url', methods=['GET'])
def get_comfyui_url():
    """
    Retorna a URL atual do ComfyUI
    """
    if comfyui_status['url']:
        return jsonify(comfyui_status), 200
    else:
        return jsonify({
            "status": "waiting",
            "message": "ComfyUI URL not yet received"
        }), 404


@app.route('/comfyui-status', methods=['GET'])
def get_status():
    """
    Retorna status completo do ComfyUI
    """
    return jsonify(comfyui_status), 200


def update_kubernetes_config(url: str):
    """
    Atualiza ConfigMap do Kubernetes com nova URL
    """
    try:
        # Verificar se kubectl está disponível
        subprocess.run(['kubectl', 'version', '--client'], 
                      capture_output=True, check=True)
        
        # Criar/atualizar ConfigMap
        configmap_yaml = f"""
apiVersion: v1
kind: ConfigMap
metadata:
  name: comfyui-config
  namespace: ai-film
data:
  COMFYUI_URL: "{url}"
  COMFYUI_UPDATED_AT: "{datetime.now().isoformat()}"
  COMFYUI_SOURCE: "colab_webhook"
"""
        
        # Salvar temporariamente
        temp_file = "/tmp/comfyui-configmap.yaml"
        with open(temp_file, 'w') as f:
            f.write(configmap_yaml)
        
        # Aplicar
        result = subprocess.run(
            ['kubectl', 'apply', '-f', temp_file],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Kubernetes ConfigMap atualizado")
            
            # Reiniciar pods que usam ComfyUI
            subprocess.run(
                ['kubectl', 'rollout', 'restart', 
                 'deployment/comfyui', '-n', 'ai-film'],
                capture_output=True
            )
            print("✅ Pods reiniciados")
        else:
            print(f"⚠️ Erro ao atualizar ConfigMap: {result.stderr}")
            
    except FileNotFoundError:
        print("⚠️ kubectl não encontrado - pulando atualização K8s")
    except Exception as e:
        print(f"⚠️ Erro ao atualizar Kubernetes: {e}")


def save_url_to_file(url: str):
    """
    Salva URL em arquivo para GitHub Actions
    """
    try:
        # Criar diretório se não existir
        os.makedirs('open3d_implementation/config', exist_ok=True)
        
        # Salvar configuração
        config = {
            "base_url": url,
            "updated_at": datetime.now().isoformat(),
            "source": "colab_webhook"
        }
        
        config_file = "open3d_implementation/config/comfyui_config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Configuração salva em: {config_file}")
        
        # Também salvar em arquivo simples para fácil leitura
        with open("/tmp/comfyui_url.txt", 'w') as f:
            f.write(url)
        
    except Exception as e:
        print(f"⚠️ Erro ao salvar arquivo: {e}")


if __name__ == '__main__':
    port = int(os.getenv('WEBHOOK_PORT', 5001))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    print("=" * 70)
    print("🎬 AI FILM PIPELINE - COLAB WEBHOOK HANDLER")
    print("=" * 70)
    print(f"\n🌐 Servidor rodando na porta: {port}")
    print(f"📡 Endpoint: http://localhost:{port}/comfyui-url")
    print(f"🔍 Status: http://localhost:{port}/comfyui-status")
    print(f"💚 Health: http://localhost:{port}/health")
    print("\n📋 Adicione ao seu Colab:")
    print(f"""
import requests
tunnel_url = "https://sua-url.trycloudflare.com"
webhook_url = "http://seu-ip:{port}/comfyui-url"
requests.post(webhook_url, json={{"url": tunnel_url}})
    """)
    print("=" * 70)
    print()
    
    app.run(host='0.0.0.0', port=port, debug=debug)
