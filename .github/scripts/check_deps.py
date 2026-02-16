#!/usr/bin/env python3
"""
Verifica dependências Python e FFmpeg
"""
import sys
import pkg_resources
import subprocess

def check_package(package_name):
    try:
        version = pkg_resources.get_distribution(package_name).version
        print(f"✅ {package_name}: {version}")
        return True
    except pkg_resources.DistributionNotFound:
        print(f"❌ {package_name}: NÃO INSTALADO")
        return False

def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            # Extrair versão do output
            first_line = result.stdout.split('\n')[0]
            print(f"✅ FFmpeg: {first_line}")
            return True
        else:
            print(f"❌ FFmpeg: Erro na execução")
            return False
    except FileNotFoundError:
        print(f"❌ FFmpeg: NÃO INSTALADO")
        return False
    except Exception as e:
        print(f"❌ FFmpeg: Erro - {e}")
        return False

print("🔍 Verificando ambiente Python...")
print(f"🐍 Python Version: {sys.version}")

packages = [
    "langchain",
    "langchain-google-genai",
    "langgraph",
    "dagster",
    "requests",
    "pillow"
]

all_ok = True
print("\n📦 Verificando pacotes Python:")
for pkg in packages:
    if not check_package(pkg):
        all_ok = False

print("\n🎬 Verificando FFmpeg:")
if not check_ffmpeg():
    all_ok = False

if all_ok:
    print("\n✅ Ambiente completo e pronto para execução!")
    sys.exit(0)
else:
    print("\n❌ Ambiente incompleto!")
    sys.exit(1)
