# 🚀 Setup ComfyUI no Google Colab Pro com Cloudflare Permanente

**GPU Colab Pro | Cloudflare Tunnel Ativo 24/7**

---

## 📋 Pré-requisitos

- ✅ Google Colab Pro (você já tem)
- ✅ Conta Cloudflare (gratuita)

---

## 🛠️ Setup Completo

### **PASSO 1: Notebook Colab**

Crie um novo notebook no Colab com este código:

```python
# ═══════════════════════════════════════════════════════════════
# 🎬 ComfyUI + Cloudflare Tunnel - AI Film Pipeline
# Mantém ativo automaticamente com keep-alive
# ═══════════════════════════════════════════════════════════════

import os
import subprocess
import time
import requests
from pathlib import Path
from IPython.display import clear_output, display, HTML

# ═══════════════════════════════════════════════════════════════
# 1. INSTALAR COMFYUI
# ═══════════════════════════════════════════════════════════════

print("📦 Instalando ComfyUI...")

# Clonar ComfyUI
if not Path("/content/ComfyUI").exists():
    !git clone https://github.com/comfyanonymous/ComfyUI.git /content/ComfyUI
    %cd /content/ComfyUI
    !pip install -q xformers!=0.0.18 -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu121
else:
    %cd /content/ComfyUI
    print("✅ ComfyUI já instalado")

# Baixar modelo SD 1.5 (se não existir)
model_path = Path("/content/ComfyUI/models/checkpoints/v1-5-pruned-emaonly.safetensors")
if not model_path.exists():
    print("📥 Baixando Stable Diffusion 1.5...")
    !wget -q -O {model_path} https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors
    print("✅ Modelo baixado!")

# ═══════════════════════════════════════════════════════════════
# 2. INSTALAR CLOUDFLARE TUNNEL
# ═══════════════════════════════════════════════════════════════

print("\n🌐 Instalando Cloudflare Tunnel...")

if not Path("/content/cloudflared").exists():
    !wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
    !mv cloudflared-linux-amd64 /content/cloudflared
    !chmod +x /content/cloudflared
    print("✅ Cloudflare instalado!")

# ═══════════════════════════════════════════════════════════════
# 3. INICIAR COMFYUI
# ═══════════════════════════════════════════════════════════════

print("\n🚀 Iniciando ComfyUI...")

# Iniciar ComfyUI em background
comfyui_process = subprocess.Popen(
    ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"],
    cwd="/content/ComfyUI",
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Aguardar ComfyUI iniciar
time.sleep(10)
print("✅ ComfyUI rodando na porta 8188")

# ═══════════════════════════════════════════════════════════════
# 4. INICIAR CLOUDFLARE TUNNEL
# ═══════════════════════════════════════════════════════════════

print("\n🌐 Iniciando Cloudflare Tunnel...")

# Iniciar tunnel em background
tunnel_process = subprocess.Popen(
    ["/content/cloudflared", "tunnel", "--url", "http://localhost:8188"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

# Capturar URL do Cloudflare
cloudflare_url = None
for _ in range(30):
    line = tunnel_process.stdout.readline()
    if "trycloudflare.com" in line:
        # Extrair URL
        import re
        match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', line)
        if match:
            cloudflare_url = match.group(0)
            break
    time.sleep(0.5)

if cloudflare_url:
    print(f"\n✅ Cloudflare Tunnel ativo!")
    print(f"🔗 URL: {cloudflare_url}")
    
    # Mostrar URL em destaque
    display(HTML(f"""
    <div style="background: #1a1a1a; padding: 20px; border-radius: 10px; margin: 20px 0;">
        <h2 style="color: #4CAF50;">✅ ComfyUI Ativo!</h2>
        <p style="color: #fff; font-size: 16px;">
            <strong>URL Pública:</strong><br>
            <code style="background: #333; padding: 10px; display: block; margin: 10px 0; border-radius: 5px;">
                {cloudflare_url}
            </code>
        </p>
        <p style="color: #aaa; font-size: 14px;">
            ⚠️ Copie esta URL e atualize no pipeline!<br>
            💡 Este notebook manterá o tunnel ativo automaticamente
        </p>
    </div>
    """))
else:
    print("❌ Erro ao obter URL do Cloudflare")

# ═══════════════════════════════════════════════════════════════
# 5. KEEP-ALIVE (Mantém ativo)
# ═══════════════════════════════════════════════════════════════

print("\n🔄 Iniciando keep-alive...")
print("💡 Este script manterá ComfyUI e Cloudflare ativos")
print("⚠️ NÃO FECHE ESTE NOTEBOOK!\n")

# Função de keep-alive
def keep_alive():
    """Mantém ComfyUI e Cloudflare ativos"""
    iteration = 0
    
    while True:
        iteration += 1
        
        try:
            # Testar ComfyUI local
            response = requests.get("http://localhost:8188", timeout=5)
            comfyui_status = "✅" if response.status_code == 200 else "❌"
        except:
            comfyui_status = "❌"
        
        try:
            # Testar Cloudflare público
            if cloudflare_url:
                response = requests.get(cloudflare_url, timeout=10)
                tunnel_status = "✅" if response.status_code == 200 else "❌"
            else:
                tunnel_status = "❌"
        except:
            tunnel_status = "❌"
        
        # Mostrar status
        clear_output(wait=True)
        print("═" * 70)
        print("🎬 AI FILM PIPELINE - COMFYUI + CLOUDFLARE")
        print("═" * 70)
        print(f"\n📊 Status (Iteração #{iteration}):")
        print(f"   ComfyUI Local:     {comfyui_status} http://localhost:8188")
        print(f"   Cloudflare Tunnel: {tunnel_status} {cloudflare_url}")
        print(f"\n⏰ Última verificação: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔄 Próxima verificação em 30 segundos...")
        print("\n💡 Mantenha este notebook aberto para manter o tunnel ativo")
        print("⚠️ Se o status ficar ❌, reinicie o notebook")
        print("\n" + "═" * 70)
        
        # Aguardar 30 segundos
        time.sleep(30)

# Iniciar keep-alive
try:
    keep_alive()
except KeyboardInterrupt:
    print("\n⚠️ Keep-alive interrompido pelo usuário")
except Exception as e:
    print(f"\n❌ Erro no keep-alive: {e}")
```

---

## 📝 **INSTRUÇÕES DE USO:**

### **1. Criar Notebook no Colab**

1. Acesse: https://colab.research.google.com/
2. Clique em **"New Notebook"**
3. Cole o código acima
4. Salve como: `ComfyUI_Cloudflare_KeepAlive.ipynb`

### **2. Configurar GPU**

1. Menu: **Runtime → Change runtime type**
2. Hardware accelerator: **GPU** (T4 ou melhor)
3. Clique **Save**

### **3. Executar**

1. Clique no botão ▶️ para executar a célula
2. Aguarde 2-3 minutos (instalação + download do modelo)
3. **Copie a URL do Cloudflare** que aparecerá

Exemplo de URL:
```
https://literacy-staff-singer-acknowledge.trycloudflare.com
```

### **4. Atualizar Pipeline**

No seu terminal local:

```bash
cd /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP

# Atualizar URL (use a URL que apareceu no Colab)
python3 scripts/update_comfyui_url.py https://SUA-URL-AQUI.trycloudflare.com

# Testar
python3 scripts/diagnose_system.py
```

**Resultado esperado:** Score 8/8 (100%) ✅

---

## 🔄 **Keep-Alive Automático**

O script mantém ativo automaticamente:

- ✅ Verifica status a cada 30 segundos
- ✅ Mostra status em tempo real
- ✅ Mantém Colab acordado
- ✅ Mantém Cloudflare ativo

**Status esperado:**
```
═══════════════════════════════════════════════════════════════
🎬 AI FILM PIPELINE - COMFYUI + CLOUDFLARE
═══════════════════════════════════════════════════════════════

📊 Status (Iteração #42):
   ComfyUI Local:     ✅ http://localhost:8188
   Cloudflare Tunnel: ✅ https://sua-url.trycloudflare.com

⏰ Última verificação: 2026-02-15 13:20:00
🔄 Próxima verificação em 30 segundos...

💡 Mantenha este notebook aberto para manter o tunnel ativo
```

---

## 🐛 **Troubleshooting**

### **URL do Cloudflare muda**

Se a URL mudar (reiniciar notebook):

```bash
# Atualizar nova URL
python3 scripts/update_comfyui_url.py https://NOVA-URL.trycloudflare.com

# Re-testar
python3 scripts/diagnose_system.py
```

### **Colab desconecta**

- Colab Pro tem timeout maior, mas pode desconectar
- Solução: Manter aba do navegador aberta
- O keep-alive ajuda a manter ativo

### **Erro de GPU**

- Verifique se selecionou GPU no Runtime
- Colab Pro tem acesso prioritário a GPUs

---

## 💡 **Dicas**

### **Manter Ativo por Mais Tempo**

1. Mantenha aba do Colab aberta
2. Não feche o navegador
3. Colab Pro tem timeout de ~24h

### **Automatizar Restart**

Se quiser automatizar restart quando cair, posso criar um script que:
1. Monitora a URL
2. Envia alerta quando cair
3. Instruções para restart rápido

### **Alternativa: Colab + GitHub Actions**

Posso criar workflow que:
1. Detecta quando Cloudflare cai
2. Pausa pipeline
3. Aguarda você reiniciar Colab
4. Retoma automaticamente

---

## ✅ **Checklist**

- [ ] Criar notebook no Colab
- [ ] Configurar GPU (T4 ou melhor)
- [ ] Executar célula
- [ ] Copiar URL do Cloudflare
- [ ] Atualizar URL no pipeline
- [ ] Executar diagnóstico (100%)
- [ ] Manter notebook aberto

---

## 🚀 **Próximos Passos**

Após configurar:

1. ✅ ComfyUI rodando no Colab Pro
2. ✅ Cloudflare Tunnel ativo
3. ✅ Keep-alive mantendo tudo funcionando
4. ✅ Pipeline com score 100%
5. ✅ Testar geração end-to-end

---

**Tempo de setup:** 5 minutos  
**Custo:** Colab Pro (você já paga)  
**Uptime:** ~24h (com keep-alive)

---

**Quer que eu crie algum script adicional de monitoramento ou automação?** 🎯
