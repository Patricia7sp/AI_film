#!/usr/bin/env python3
"""
Script para verificar quais samplers estão disponíveis no ComfyUI
"""

import requests
import json
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def check_available_samplers():
    """Verifica quais samplers estão disponíveis no ComfyUI"""
    
    # Obter URL do ComfyUI
    comfyui_url = os.getenv('COMFYUI_HOST', 'http://127.0.0.1:8188')
    if not comfyui_url.startswith('http'):
        comfyui_url = f'http://{comfyui_url}'
    
    print(f"Verificando samplers disponíveis em: {comfyui_url}")
    
    try:
        # Endpoint para obter informações sobre os nós disponíveis
        response = requests.get(f"{comfyui_url}/object_info")
        
        if response.status_code == 200:
            data = response.json()
            
            # Procurar pelo KSampler
            if 'KSampler' in data:
                ksampler_info = data['KSampler']
                if 'input' in ksampler_info and 'required' in ksampler_info['input']:
                    sampler_info = ksampler_info['input']['required']
                    
                    if 'sampler_name' in sampler_info:
                        available_samplers = sampler_info['sampler_name'][0]
                        print(f"\n✅ Samplers disponíveis ({len(available_samplers)}):")
                        for i, sampler in enumerate(available_samplers, 1):
                            print(f"  {i:2d}. {sampler}")
                        
                        # Verificar se DPM++ 2M Karras está disponível
                        if "DPM++ 2M Karras" in available_samplers:
                            print(f"\n✅ 'DPM++ 2M Karras' está DISPONÍVEL!")
                        else:
                            print(f"\n❌ 'DPM++ 2M Karras' NÃO está disponível")
                            
                            # Sugerir alternativas de alta qualidade
                            high_quality_alternatives = [
                                "DPM++ 2M",
                                "DPM++ SDE Karras", 
                                "DPM++ 2S a Karras",
                                "UniPC",
                                "DDIM"
                            ]
                            
                            print("\n🔍 Alternativas de alta qualidade encontradas:")
                            for alt in high_quality_alternatives:
                                if alt in available_samplers:
                                    print(f"  ✅ {alt}")
                        
                        return available_samplers
                    
                    if 'scheduler' in sampler_info:
                        available_schedulers = sampler_info['scheduler'][0]
                        print(f"\n✅ Schedulers disponíveis ({len(available_schedulers)}):")
                        for i, scheduler in enumerate(available_schedulers, 1):
                            print(f"  {i:2d}. {scheduler}")
                        
                        return available_samplers, available_schedulers
            
            print("❌ Informações do KSampler não encontradas")
            return None
            
        else:
            print(f"❌ Erro ao conectar: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Erro ao verificar samplers: {e}")
        return None

if __name__ == "__main__":
    print("🔍 Verificando samplers disponíveis no ComfyUI...")
    result = check_available_samplers()
    
    if result:
        print(f"\n✅ Verificação concluída!")
    else:
        print(f"\n❌ Falha na verificação")
