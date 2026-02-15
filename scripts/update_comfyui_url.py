#!/usr/bin/env python3
"""
Script para atualizar URL do ComfyUI no .env
"""
import os
from pathlib import Path

def update_comfyui_url(new_url: str):
    """Atualiza COMFYUI_URL no arquivo .env"""
    env_file = Path(__file__).parent.parent / 'open3d_implementation' / '.env'
    
    if not env_file.exists():
        print(f"❌ Arquivo .env não encontrado: {env_file}")
        return False
    
    # Ler arquivo
    with open(env_file, 'r') as f:
        lines = f.readlines()
    
    # Atualizar ou adicionar COMFYUI_URL
    updated = False
    for i, line in enumerate(lines):
        if line.startswith('COMFYUI_URL='):
            lines[i] = f'COMFYUI_URL={new_url}\n'
            updated = True
            break
    
    if not updated:
        lines.append(f'\nCOMFYUI_URL={new_url}\n')
    
    # Salvar
    with open(env_file, 'w') as f:
        f.writelines(lines)
    
    print(f"✅ COMFYUI_URL atualizada!")
    print(f"   Nova URL: {new_url}")
    print(f"   Arquivo: {env_file}")
    return True

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("❌ Uso: python3 update_comfyui_url.py <URL>")
        print("\nExemplo:")
        print("  python3 scripts/update_comfyui_url.py https://seu-username-comfyui-ai-film-pipeline.hf.space")
        sys.exit(1)
    
    new_url = sys.argv[1]
    
    if not new_url.startswith('http'):
        print("❌ URL deve começar com http:// ou https://")
        sys.exit(1)
    
    if update_comfyui_url(new_url):
        print("\n🔍 Execute o diagnóstico para validar:")
        print("   python3 scripts/diagnose_system.py")
