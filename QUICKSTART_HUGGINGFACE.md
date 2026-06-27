# ⚡ Quick Start - ComfyUI Hugging Face (Gradio)

**Setup em 10 minutos com GPU T4 gratuita!**

---

## 🚀 Passos Rápidos

### 1️⃣ Criar Space (1 min)

```
1. Acesse: https://huggingface.co/spaces
2. Clique "Create new Space"
3. Configure:
   - Name: comfyui-ai-film
   - SDK: Gradio (não Docker!)
   - Hardware: GPU T4 (free)
4. Clique "Create Space"
```

### 2️⃣ Criar app.py (2 min)

Copie o código completo de: `HUGGINGFACE_GRADIO_SETUP.md`

Ou use este código mínimo:

```python
import gradio as gr
import subprocess
import sys
from pathlib import Path

def setup_comfyui():
    comfyui_path = Path("/tmp/ComfyUI")
    if not comfyui_path.exists():
        subprocess.run(["git", "clone", "https://github.com/comfyanonymous/ComfyUI.git", str(comfyui_path)])
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "torch", "torchvision", "--index-url", "https://download.pytorch.org/whl/cu118"])
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", f"{comfyui_path}/requirements.txt"])
    return comfyui_path

comfyui_path = setup_comfyui()

# Iniciar servidor
subprocess.Popen([sys.executable, "main.py", "--listen", "0.0.0.0", "--port", "8188"], cwd=str(comfyui_path))

demo = gr.Interface(
    fn=lambda x: "ComfyUI rodando em http://localhost:8188",
    inputs="text",
    outputs="text",
    title="ComfyUI AI Film Pipeline"
)

demo.launch(server_name="0.0.0.0", server_port=7860)
```

### 3️⃣ Criar requirements.txt (30 seg)

```txt
gradio
requests
torch
torchvision
```

### 4️⃣ Deploy (10 min)

```
1. Clique "Commit to main"
2. Aguarde build (10 min)
3. Space iniciará automaticamente
```

### 5️⃣ Obter URL (30 seg)

Sua URL será:
```
https://SEU_USERNAME-comfyui-ai-film.hf.space
```

### 6️⃣ Atualizar Pipeline (1 min)

```bash
cd /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP

python3 scripts/update_comfyui_url.py https://SEU_USERNAME-comfyui-ai-film.hf.space

python3 scripts/diagnose_system.py
```

**Resultado esperado:** Score 8/8 (100%) ✅

---

## 🎯 Resultado

- ✅ ComfyUI com GPU T4 gratuita
- ✅ Interface Gradio para testes
- ✅ API disponível
- ✅ URL permanente
- ✅ Pipeline 100% funcional

---

## 📚 Documentação Completa

Ver: `HUGGINGFACE_GRADIO_SETUP.md`

---

**Tempo total:** ~15 minutos  
**Custo:** $0 🎉
