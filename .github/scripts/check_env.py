#!/usr/bin/env python3
"""
Verifica variáveis de ambiente necessárias
"""
import os
import sys

def check_env():
    """Verifica se todas as variáveis necessárias estão configuradas"""
    required_vars = {
        'GEMINI_API_KEY': 'API do Google Gemini',
        'COMFYUI_URL': 'URL do ComfyUI',
    }
    
    optional_vars = {
        'OPENAI_API_KEY': 'API da OpenAI (fallback)',
        'ELEVENLABS_API_KEY': 'API do ElevenLabs (áudio)',
    }
    
    print("🔍 Verificando variáveis de ambiente...")
    print("=" * 60)
    
    missing = []
    
    # Verificar obrigatórias
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: Configurado ({desc})")
        else:
            print(f"❌ {var}: FALTANDO ({desc})")
            missing.append(var)
    
    # Verificar opcionais
    for var, desc in optional_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: Configurado ({desc})")
        else:
            print(f"⚠️  {var}: Não configurado ({desc}) - opcional")
    
    print("=" * 60)
    
    if missing:
        print(f"\n❌ Faltam {len(missing)} variáveis obrigatórias:")
        for var in missing:
            print(f"   - {var}")
        print("\n💡 Configure no GitHub Secrets")
        sys.exit(1)
    else:
        print("\n✅ Todas as variáveis obrigatórias estão configuradas!")
        sys.exit(0)

if __name__ == '__main__':
    check_env()
