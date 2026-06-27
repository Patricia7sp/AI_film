#!/usr/bin/env python3
"""
🔍 Monitor de Cloudflare Tunnel
Monitora a URL do ComfyUI e avisa quando cair
"""
import os
import sys
import time
import requests
from pathlib import Path
from datetime import datetime

class CloudflareMonitor:
    def __init__(self):
        self.env_file = Path(__file__).parent.parent / 'open3d_implementation' / '.env'
        self.comfyui_url = self.get_comfyui_url()
        self.consecutive_failures = 0
        self.max_failures = 3
        
    def get_comfyui_url(self):
        """Lê URL do ComfyUI do .env"""
        if not self.env_file.exists():
            print(f"❌ Arquivo .env não encontrado: {self.env_file}")
            sys.exit(1)
        
        with open(self.env_file) as f:
            for line in f:
                if line.startswith('COMFYUI_URL='):
                    url = line.split('=', 1)[1].strip()
                    return url
        
        print("❌ COMFYUI_URL não encontrada no .env")
        sys.exit(1)
    
    def check_status(self):
        """Verifica se ComfyUI está acessível"""
        try:
            response = requests.get(self.comfyui_url, timeout=10)
            if response.status_code == 200:
                self.consecutive_failures = 0
                return True, "Online"
            else:
                self.consecutive_failures += 1
                return False, f"HTTP {response.status_code}"
        except requests.exceptions.Timeout:
            self.consecutive_failures += 1
            return False, "Timeout"
        except requests.exceptions.ConnectionError:
            self.consecutive_failures += 1
            return False, "Connection Error"
        except Exception as e:
            self.consecutive_failures += 1
            return False, str(e)[:30]
    
    def monitor(self, interval=30):
        """Monitora continuamente"""
        print("═" * 70)
        print("🔍 MONITOR DE CLOUDFLARE TUNNEL")
        print("═" * 70)
        print(f"\n📡 Monitorando: {self.comfyui_url}")
        print(f"⏱️  Intervalo: {interval} segundos")
        print(f"⚠️  Alertas após {self.max_failures} falhas consecutivas\n")
        print("💡 Pressione Ctrl+C para parar\n")
        print("═" * 70)
        
        iteration = 0
        last_status = None
        
        try:
            while True:
                iteration += 1
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                is_online, status_msg = self.check_status()
                
                # Detectar mudança de status
                if last_status is not None and last_status != is_online:
                    if is_online:
                        print(f"\n✅ [{timestamp}] RECUPERADO! ComfyUI voltou online")
                        print("   " + "─" * 66)
                    else:
                        print(f"\n❌ [{timestamp}] FALHA DETECTADA! ComfyUI offline")
                        print("   " + "─" * 66)
                
                # Status atual
                status_icon = "✅" if is_online else "❌"
                print(f"{status_icon} [{timestamp}] #{iteration:04d} - {status_msg}", end="")
                
                # Alerta se muitas falhas
                if self.consecutive_failures >= self.max_failures:
                    print(f" ⚠️  {self.consecutive_failures} falhas!")
                    if self.consecutive_failures == self.max_failures:
                        self.send_alert()
                else:
                    print()
                
                last_status = is_online
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Monitor interrompido pelo usuário")
            print("═" * 70)
    
    def send_alert(self):
        """Envia alerta quando Cloudflare cai"""
        print("\n")
        print("╔" + "═" * 68 + "╗")
        print("║" + " " * 20 + "⚠️  ALERTA CRÍTICO  ⚠️" + " " * 25 + "║")
        print("╚" + "═" * 68 + "╝")
        print("\n🚨 ComfyUI está OFFLINE!")
        print(f"   URL: {self.comfyui_url}")
        print(f"   Falhas consecutivas: {self.consecutive_failures}")
        print("\n🔧 AÇÕES NECESSÁRIAS:")
        print("   1. Verifique se o notebook do Colab está rodando")
        print("   2. Verifique se o Cloudflare Tunnel está ativo")
        print("   3. Se necessário, reinicie o notebook")
        print("   4. Atualize a URL se mudou:")
        print(f"      python3 scripts/update_comfyui_url.py https://NOVA-URL.trycloudflare.com")
        print("\n" + "═" * 70 + "\n")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor de Cloudflare Tunnel')
    parser.add_argument(
        '--interval',
        type=int,
        default=30,
        help='Intervalo entre verificações em segundos (padrão: 30)'
    )
    
    args = parser.parse_args()
    
    monitor = CloudflareMonitor()
    monitor.monitor(interval=args.interval)
