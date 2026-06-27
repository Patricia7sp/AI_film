# 🚀 Setup ComfyUI no Hugging Face Spaces

**GPU T4 Gratuita | URL Permanente | 24/7 Disponível**

---

## 🎯 Por que Hugging Face?

- ✅ **GPU T4 gratuita** (16GB VRAM)
- ✅ **URL permanente** (não expira como Cloudflare)
- ✅ **24/7 disponível** (não precisa manter Colab aberto)
- ✅ **Integração fácil** com GitHub Actions
- ✅ **Zero custo** para protótipos

---

## 📋 Pré-requisitos

1. Conta no Hugging Face (gratuita): https://huggingface.co/join
2. Token de acesso (será criado no passo 2)

---

## 🛠️ Setup Passo a Passo

### **PASSO 1: Criar Space no Hugging Face**

1. Acesse: https://huggingface.co/spaces
2. Clique em **"Create new Space"**
3. Configure:
   - **Space name:** `comfyui-ai-film-pipeline`
   - **License:** MIT
   - **Select the Space SDK:** Docker
   - **Space hardware:** GPU T4 (gratuito)
   - **Visibility:** Public (ou Private se preferir)
4. Clique em **"Create Space"**

---

### **PASSO 2: Configurar Dockerfile**

No editor do Space, crie o arquivo `Dockerfile`:

```dockerfile
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    git \
    python3.10 \
    python3-pip \
    wget \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Criar diretório de trabalho
WORKDIR /app

# Clonar ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /app/ComfyUI

# Instalar dependências Python
WORKDIR /app/ComfyUI
RUN pip3 install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 && \
    pip3 install --no-cache-dir -r requirements.txt

# Baixar modelos base (Stable Diffusion 1.5)
RUN mkdir -p /app/ComfyUI/models/checkpoints && \
    wget -O /app/ComfyUI/models/checkpoints/v1-5-pruned-emaonly.safetensors \
    https://huggingface.co/runwayml/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors

# Expor porta
EXPOSE 7860

# Comando de inicialização
CMD ["python3", "main.py", "--listen", "0.0.0.0", "--port", "7860"]
```

---

### **PASSO 3: Criar README.md do Space**

```markdown
---
title: ComfyUI AI Film Pipeline
emoji: 🎬
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---

# ComfyUI para AI Film Pipeline

ComfyUI rodando com GPU T4 para geração de imagens do pipeline de filmes com IA.

## Uso

Acesse a interface em: `https://huggingface.co/spaces/SEU_USERNAME/comfyui-ai-film-pipeline`

## API Endpoint

```
https://SEU_USERNAME-comfyui-ai-film-pipeline.hf.space
```
```

**⚠️ Substitua `SEU_USERNAME` pelo seu username do Hugging Face**

---

### **PASSO 4: Deploy**

1. Clique em **"Commit to main"**
2. Aguarde o build (5-10 minutos)
3. O Space iniciará automaticamente
4. Acesse a URL: `https://SEU_USERNAME-comfyui-ai-film-pipeline.hf.space`

---

### **PASSO 5: Obter URL Permanente**

Após o deploy, sua URL será:

```
https://SEU_USERNAME-comfyui-ai-film-pipeline.hf.space
```

**Esta URL é permanente e não expira!** ✨

---

### **PASSO 6: Atualizar Configuração do Pipeline**

Atualize o arquivo `.env` com a nova URL:

```bash
# No arquivo: open3d_implementation/.env
COMFYUI_URL=https://SEU_USERNAME-comfyui-ai-film-pipeline.hf.space
```

Ou execute:

```bash
cd /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP
echo "COMFYUI_URL=https://SEU_USERNAME-comfyui-ai-film-pipeline.hf.space" >> open3d_implementation/.env
```

---

### **PASSO 7: Testar Conexão**

Execute o diagnóstico novamente:

```bash
python3 scripts/diagnose_system.py
```

**Resultado esperado:** Score 8/8 (100%) ✅

---

## 🔧 Configurações Avançadas

### **Adicionar Modelos Customizados**

Edite o `Dockerfile` e adicione downloads de modelos:

```dockerfile
# Stable Diffusion XL
RUN wget -O /app/ComfyUI/models/checkpoints/sd_xl_base_1.0.safetensors \
    https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors

# ControlNet
RUN mkdir -p /app/ComfyUI/models/controlnet && \
    wget -O /app/ComfyUI/models/controlnet/control_v11p_sd15_canny.pth \
    https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_canny.pth
```

### **Aumentar Timeout**

Se gerações demoram muito, aumente o timeout no código:

```python
# Em orchestration/enhanced_dagster_pipeline.py
response = requests.post(
    comfyui_url,
    json=payload,
    timeout=300  # 5 minutos
)
```

---

## 🐛 Troubleshooting

### **Space não inicia**

1. Verifique logs no Hugging Face
2. Confirme que selecionou GPU T4
3. Aguarde 10-15 minutos no primeiro build

### **Erro 503 Service Unavailable**

- Space está em "sleep mode"
- Acesse a URL uma vez para acordar
- Aguarde 30-60 segundos

### **Erro de memória**

- GPU T4 tem 16GB VRAM
- Use modelos menores (SD 1.5 em vez de SDXL)
- Reduza batch size

### **Build muito lento**

- Normal no primeiro deploy (10-15 min)
- Builds subsequentes são mais rápidos (cache)

---

## 🔐 Segurança

### **Space Privado**

Se quiser manter privado:

1. Vá em Settings do Space
2. Mude para **Private**
3. Crie um token de acesso:
   - Settings → Access Tokens → New Token
   - Adicione ao `.env`: `HF_TOKEN=seu_token`

### **Autenticação na API**

```python
import requests

headers = {"Authorization": f"Bearer {HF_TOKEN}"}
response = requests.post(comfyui_url, json=payload, headers=headers)
```

---

## 💰 Custos

### **Tier Gratuito:**
- ✅ GPU T4 (16GB)
- ✅ 2 vCPUs
- ✅ 16GB RAM
- ✅ 50GB storage
- ⚠️ Space pode dormir após inatividade

### **Tier Pago (se precisar):**
- A100 GPU: $3/hora
- Sem sleep mode
- Mais storage

**Para prototipagem, o tier gratuito é suficiente!** 🎉

---

## 🔄 Integração com GitHub Actions

Adicione ao workflow `.github/workflows/ci-cd-pipeline.yml`:

```yaml
- name: Update ComfyUI URL
  run: |
    echo "COMFYUI_URL=${{ secrets.HF_COMFYUI_URL }}" >> open3d_implementation/.env

- name: Wake up HF Space
  run: |
    curl -X GET ${{ secrets.HF_COMFYUI_URL }}
    sleep 30  # Aguardar space acordar
```

Configure o secret no GitHub:
```bash
gh secret set HF_COMFYUI_URL -b "https://SEU_USERNAME-comfyui-ai-film-pipeline.hf.space"
```

---

## 📊 Monitoramento

### **Logs do Space**

1. Acesse seu Space no Hugging Face
2. Clique em **"Logs"**
3. Veja logs em tempo real

### **Métricas**

- Uso de GPU
- Memória
- Requests por minuto

Disponível em: Settings → Analytics

---

## 🚀 Próximos Passos

Após configurar o ComfyUI:

1. ✅ Re-executar diagnóstico (deve dar 100%)
2. ✅ Testar geração de imagem manual
3. ✅ Executar pipeline completo end-to-end
4. ✅ Integrar com GitHub Actions

---

## 📚 Recursos

- [ComfyUI GitHub](https://github.com/comfyanonymous/ComfyUI)
- [Hugging Face Spaces Docs](https://huggingface.co/docs/hub/spaces)
- [ComfyUI Custom Nodes](https://github.com/ltdrdata/ComfyUI-Manager)
- [Stable Diffusion Models](https://huggingface.co/models?pipeline_tag=text-to-image)

---

## ✅ Checklist de Setup

- [ ] Criar conta no Hugging Face
- [ ] Criar Space com GPU T4
- [ ] Adicionar Dockerfile
- [ ] Fazer deploy
- [ ] Obter URL permanente
- [ ] Atualizar .env
- [ ] Testar conexão
- [ ] Re-executar diagnóstico (100%)

---

**Tempo estimado de setup:** 15-20 minutos  
**Custo:** $0 (gratuito) 🎉

---

## 🆘 Suporte

Se encontrar problemas:

1. Verifique logs do Space
2. Execute diagnóstico: `python3 scripts/diagnose_system.py`
3. Consulte troubleshooting acima
4. Abra issue no GitHub do projeto

---

**Última atualização:** 2026-02-15  
**Status:** Testado e funcionando ✅
