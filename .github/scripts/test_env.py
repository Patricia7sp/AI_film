#!/usr/bin/env python3
"""
Testa se as variáveis de ambiente estão configuradas
"""
import os

print("🔍 TESTE DE VARIÁVEIS DE AMBIENTE")
print("=" * 50)

# Variáveis obrigatórias
required = {
    'GEMINI_API_KEY': 'API do Google Gemini',
    'COMFYUI_URL': 'URL do ComfyUI',
}

# Variáveis opcionais (mas importantes)
optional = {
    'OPENAI_API_KEY': 'API da OpenAI (fallback)',
    'ELEVENLABS_API_KEY': 'API do ElevenLabs (áudio)',
    'STABILITY_API_KEY': 'API do Stability AI',
    'REPLICATE_API_TOKEN': 'Token do Replicate',
}

print("\n📋 VARIÁVEIS OBRIGATÓRIAS:")
missing_required = []
for var, desc in required.items():
    value = os.getenv(var)
    if value:
        # Mostrar apenas primeiros caracteres para segurança
        masked = value[:8] + "..." if len(value) > 8 else value
        print(f"✅ {var}: {masked} ({desc})")
    else:
        print(f"❌ {var}: FALTANDO ({desc})")
        missing_required.append(var)

print("\n📋 VARIÁVEIS OPCIONAL:")
for var, desc in optional.items():
    value = os.getenv(var)
    if value:
        # Mostrar apenas primeiros caracteres para segurança
        masked = value[:8] + "..." if len(value) > 8 else value
        print(f"✅ {var}: {masked} ({desc})")
    else:
        print(f"⚠️  {var}: Não configurada ({desc})")

print("\n" + "=" * 50)

if missing_required:
    print(f"❌ FALTAM {len(missing_required)} variáveis obrigatórias!")
    print("Configure no GitHub Secrets:")
    for var in missing_required:
        print(f"   - {var}")
    exit(1)
else:
    print("✅ Todas as variáveis obrigatórias estão OK!")
    
    # Verificar se ElevenLabs está disponível (importante para áudio)
    elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')
    if elevenlabs_key:
        print("🎙️ ElevenLabs disponível para geração de áudio!")
    else:
        print("⚠️  ElevenLabs não configurado - áudio será mock")
    
    exit(0)
