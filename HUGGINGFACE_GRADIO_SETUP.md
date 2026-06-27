# 🚀 ComfyUI no Hugging Face com Gradio + GPU

**GPU T4 Gratuita | Setup em 10 minutos**

---

## 🎯 Setup com Gradio (GPU Gratuita)

### **PASSO 1: Criar Space**

1. Acesse: https://huggingface.co/spaces
2. Clique **"Create new Space"**
3. Configure:
   - **Name:** `comfyui-ai-film`
   - **SDK:** Gradio
   - **Hardware:** GPU T4 (free)
   - **Visibility:** Public
4. Clique **"Create Space"**

---

### **PASSO 2: Criar app.py**

Cole este código no editor:

```python
import gradio as gr
import subprocess
import os
import sys
import time
import requests
from pathlib import Path

# Instalar ComfyUI na primeira execução
def setup_comfyui():
    comfyui_path = Path("/tmp/ComfyUI")
    
    if not comfyui_path.exists():
        print("📦 Instalando ComfyUI...")
        subprocess.run(["git", "clone", "https://github.com/comfyanonymous/ComfyUI.git", str(comfyui_path)])
        
        # Instalar dependências
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "torch", "torchvision", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu118"])
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", f"{comfyui_path}/requirements.txt"])
        
        # Baixar modelo SD 1.5
        models_dir = comfyui_path / "models" / "checkpoints"
        models_dir.mkdir(parents=True, exist_ok=True)
        
        model_path = models_dir / "v1-5-pruned-emaonly.safetensors"
        if not model_path.exists():
            print("📥 Baixando Stable Diffusion 1.5...")
            subprocess.run([
                "wget", "-q", "-O", str(model_path),
                "https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors"
            ])
        
        print("✅ ComfyUI instalado!")
    
    return comfyui_path

# Iniciar servidor ComfyUI
def start_comfyui_server():
    comfyui_path = setup_comfyui()
    
    # Iniciar servidor em background
    process = subprocess.Popen(
        [sys.executable, "main.py", "--listen", "0.0.0.0", "--port", "8188"],
        cwd=str(comfyui_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Aguardar servidor iniciar
    print("⏳ Aguardando ComfyUI iniciar...")
    for i in range(30):
        try:
            response = requests.get("http://localhost:8188")
            if response.status_code == 200:
                print("✅ ComfyUI rodando!")
                return process
        except:
            time.sleep(1)
    
    return process

# Iniciar servidor ao carregar
print("🚀 Iniciando ComfyUI...")
server_process = start_comfyui_server()

# Interface Gradio
def generate_image(prompt, negative_prompt="", steps=20, cfg=7.0):
    """Gera imagem usando ComfyUI"""
    
    workflow = {
        "3": {
            "inputs": {
                "seed": 42,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0]
            },
            "class_type": "KSampler"
        },
        "4": {
            "inputs": {
                "ckpt_name": "v1-5-pruned-emaonly.safetensors"
            },
            "class_type": "CheckpointLoaderSimple"
        },
        "5": {
            "inputs": {
                "width": 512,
                "height": 512,
                "batch_size": 1
            },
            "class_type": "EmptyLatentImage"
        },
        "6": {
            "inputs": {
                "text": prompt,
                "clip": ["4", 1]
            },
            "class_type": "CLIPTextEncode"
        },
        "7": {
            "inputs": {
                "text": negative_prompt,
                "clip": ["4", 1]
            },
            "class_type": "CLIPTextEncode"
        },
        "8": {
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2]
            },
            "class_type": "VAEDecode"
        },
        "9": {
            "inputs": {
                "filename_prefix": "ComfyUI",
                "images": ["8", 0]
            },
            "class_type": "SaveImage"
        }
    }
    
    try:
        # Enviar workflow
        response = requests.post(
            "http://localhost:8188/prompt",
            json={"prompt": workflow}
        )
        
        if response.status_code == 200:
            result = response.json()
            prompt_id = result.get("prompt_id")
            
            # Aguardar geração
            for _ in range(60):
                time.sleep(1)
                history = requests.get(f"http://localhost:8188/history/{prompt_id}")
                if history.status_code == 200:
                    data = history.json()
                    if prompt_id in data:
                        outputs = data[prompt_id].get("outputs", {})
                        if "9" in outputs:
                            images = outputs["9"].get("images", [])
                            if images:
                                img_info = images[0]
                                img_path = f"/tmp/ComfyUI/output/{img_info['filename']}"
                                if os.path.exists(img_path):
                                    return img_path
            
            return "⏳ Timeout - tente novamente"
        else:
            return f"❌ Erro: {response.status_code}"
    
    except Exception as e:
        return f"❌ Erro: {str(e)}"

# Interface
with gr.Blocks(title="ComfyUI AI Film Pipeline") as demo:
    gr.Markdown("# 🎬 ComfyUI - AI Film Pipeline")
    gr.Markdown("**GPU T4 | Stable Diffusion 1.5**")
    
    with gr.Row():
        with gr.Column():
            prompt = gr.Textbox(
                label="Prompt",
                placeholder="a beautiful landscape, mountains, sunset",
                lines=3
            )
            negative_prompt = gr.Textbox(
                label="Negative Prompt",
                placeholder="blurry, low quality",
                lines=2
            )
            
            with gr.Row():
                steps = gr.Slider(10, 50, value=20, step=1, label="Steps")
                cfg = gr.Slider(1, 20, value=7, step=0.5, label="CFG Scale")
            
            generate_btn = gr.Button("🎨 Generate Image", variant="primary")
        
        with gr.Column():
            output = gr.Image(label="Generated Image", type="filepath")
    
    generate_btn.click(
        fn=generate_image,
        inputs=[prompt, negative_prompt, steps, cfg],
        outputs=output
    )
    
    gr.Markdown("---")
    gr.Markdown("**API Endpoint:** Use a URL deste Space para integração")
    gr.Markdown("**Status:** ComfyUI rodando em http://localhost:8188")

# Iniciar
demo.launch(server_name="0.0.0.0", server_port=7860)
```

---

### **PASSO 3: Criar requirements.txt**

```txt
gradio
requests
torch
torchvision
torchaudio
```

---

### **PASSO 4: Deploy**

1. Clique **"Commit to main"**
2. Aguarde build (5-10 min)
3. Space iniciará automaticamente

---

### **PASSO 5: Obter URL**

Sua URL será:
```
https://huggingface.co/spaces/SEU_USERNAME/comfyui-ai-film
```

**Para API, use:**
```
https://SEU_USERNAME-comfyui-ai-film.hf.space
```

---

### **PASSO 6: Atualizar Pipeline**

```bash
cd /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP

# Atualizar URL (usar URL do Space, não a interface Gradio)
python3 scripts/update_comfyui_url.py https://SEU_USERNAME-comfyui-ai-film.hf.space

# Testar
python3 scripts/diagnose_system.py
```

---

## 🔧 Integração com Pipeline

O pipeline precisa enviar requisições para o endpoint ComfyUI. Atualize o código:

```python
# Em orchestration/enhanced_dagster_pipeline.py

import requests

def generate_image_comfyui(prompt: str, comfyui_url: str):
    """Gera imagem via ComfyUI no Hugging Face"""
    
    # Endpoint do ComfyUI (não do Gradio)
    endpoint = f"{comfyui_url}/prompt"
    
    workflow = {
        # ... seu workflow aqui ...
    }
    
    response = requests.post(endpoint, json={"prompt": workflow}, timeout=300)
    return response.json()
```

---

## 🎯 Vantagens do Gradio

- ✅ GPU T4 gratuita (funciona!)
- ✅ Interface visual para testes
- ✅ API disponível automaticamente
- ✅ Setup mais simples que Docker
- ✅ Logs visíveis no Space

---

## 🐛 Troubleshooting

### **Space não inicia**
- Aguarde 10-15 min no primeiro build
- Verifique logs no Space

### **Erro de memória**
- GPU T4 tem 16GB VRAM
- Use SD 1.5 (não SDXL)

### **Timeout na geração**
- Primeira geração demora (carrega modelo)
- Gerações seguintes são rápidas

---

## 📊 Teste Manual

1. Acesse a interface do Space
2. Digite um prompt: "a beautiful landscape"
3. Clique "Generate Image"
4. Aguarde 30-60 segundos
5. Imagem aparecerá

---

## ✅ Próximos Passos

Após configurar:

1. Testar interface manual
2. Atualizar URL no pipeline
3. Re-executar diagnóstico (100%)
4. Testar pipeline completo

---

**Tempo:** 10-15 minutos  
**Custo:** $0 (gratuito) 🎉
