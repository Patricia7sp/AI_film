#!/usr/bin/env python3
"""
Diagnóstico completo de variáveis de ambiente no GitHub Actions
"""
import os

print("🔍 DIAGNÓSTICO COMPLETO DE VARIÁVEIS DE AMBIENTE")
print("=" * 60)

# Lista de todas as variáveis que esperamos
expected_vars = {
    'GEMINI_API_KEY': 'API do Google Gemini',
    'GOOGLE_API_KEY': 'API do Google (backup)',
    'OPENAI_API_KEY': 'API da OpenAI',
    'ELEVENLABS_API_KEY': 'API do ElevenLabs',
    'STABILITY_API_KEY': 'API do Stability AI',
    'REPLICATE_API_TOKEN': 'Token do Replicate',
    'COMFYUI_URL': 'URL do ComfyUI',
    'STORY_INPUT': 'História de entrada',
}

print("\n📋 VARIÁVEIS ESPERADAS:")
present_vars = {}
missing_vars = {}

for var, desc in expected_vars.items():
    value = os.getenv(var)
    if value:
        # Mascara valores sensíveis
        if 'API_KEY' in var or 'TOKEN' in var:
            masked = value[:8] + "..." if len(value) > 8 else "***"
        else:
            # Para variáveis não sensíveis, mostra mais
            masked = value[:50] + "..." if len(value) > 50 else value
        
        present_vars[var] = {
            'value': value,
            'masked': masked,
            'desc': desc,
            'length': len(value)
        }
        print(f"✅ {var}: {masked} ({len(value)} chars) - {desc}")
    else:
        missing_vars[var] = desc
        print(f"❌ {var}: FALTANDO - {desc}")

print("\n" + "=" * 60)
print("🔍 ANÁLISE DAS VARIÁVEIS PRESENTES:")

# Análise específica das variáveis importantes
if 'ELEVENLABS_API_KEY' in present_vars:
    key = present_vars['ELEVENLABS_API_KEY']
    print(f"\n🎙️ ELEVENLABS_API_KEY:")
    print(f"   ✅ Presente: {key['masked']}")
    print(f"   📏 Tamanho: {key['length']} caracteres")
    print(f"   📝 Descrição: {key['desc']}")
    
    # Validação básica
    if key['length'] > 20:
        print("   ✅ Parece uma API Key válida (tamanho > 20)")
    else:
        print("   ⚠️  Tamanho suspeito para API Key")
        
    if key['value'].startswith('sk-'):
        print("   ✅ Formato típico de API Key (começa com sk-)")
    else:
        print("   ⚠️  Formato não típico (não começa com sk-)")
else:
    print(f"\n🎙️ ELEVENLABS_API_KEY: ❌ NÃO ENCONTRADA")
    print("   💡 Verifique se foi adicionada nos GitHub Secrets")

if 'GEMINI_API_KEY' in present_vars:
    print(f"\n🤖 GEMINI_API_KEY: ✅ Presente ({present_vars['GEMINI_API_KEY']['length']} chars)")
else:
    print(f"\n🤖 GEMINI_API_KEY: ❌ NÃO ENCONTRADA")

if 'COMFYUI_URL' in present_vars:
    url = present_vars['COMFYUI_URL']
    print(f"\n🔗 COMFYUI_URL: ✅ {url['masked']}")
    if 'trycloudflare.com' in url['value']:
        print("   ✅ URL do Cloudflare Tunnel detectada")
    else:
        print("   ℹ️  URL direta detectada")
else:
    print(f"\n🔗 COMFYUI_URL: ❌ NÃO ENCONTRADA")

print("\n" + "=" * 60)
print("📊 RESUMO:")
print(f"   ✅ Variáveis presentes: {len(present_vars)}")
print(f"   ❌ Variáveis faltando: {len(missing_vars)}")

if missing_vars:
    print(f"\n⚠️  VARIÁVEIS FALTANDO:")
    for var, desc in missing_vars.items():
        print(f"   - {var}: {desc}")

print(f"\n🎯 IMPACTO NO PIPELINE:")
if 'ELEVENLABS_API_KEY' in present_vars:
    print("   🎙️ Áudio: REAL (ElevenLabs)")
else:
    print("   🎙️ Áudio: MOCK (sem ElevenLabs)")

if 'GEMINI_API_KEY' in present_vars:
    print("   🤖 LLM: REAL (Gemini)")
else:
    print("   🤖 LLM: FALHA (sem Gemini)")

if 'COMFYUI_URL' in present_vars:
    print("   🖼️ Imagens: REAL (ComfyUI)")
else:
    print("   🖼️ Imagens: FALHA (sem ComfyUI)")

print("\n" + "=" * 60)
