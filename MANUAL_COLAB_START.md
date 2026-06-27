# 🚀 Como Iniciar o Pipeline Manualmente

## ❌ **Problema:**
O workflow esperou pela URL do ComfyUI, mas o Colab não foi iniciado automaticamente.

## ✅ **Solução Rápida (5 minutos):**

### **PASSO 1: Iniciar Colab**

1. Abra o notebook: `colab_automated_notebook.ipynb`
2. Upload para Google Colab: https://colab.research.google.com/
3. Configure GPU: Runtime → Change runtime type → GPU
4. Execute todas as células (Runtime → Run all)
5. Aguarde 2-3 minutos

### **PASSO 2: Copiar URL do Cloudflare**

O notebook mostrará algo como:
```
✅ Cloudflare Tunnel ativo!
🔗 URL: https://abc-def-ghi.trycloudflare.com
```

**Copie essa URL!**

### **PASSO 3: Atualizar URL Localmente**

```bash
cd /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP

# Atualizar URL
python3 scripts/update_comfyui_url.py https://SUA-URL-AQUI.trycloudflare.com

# Commit e push
git add open3d_implementation/.env
git commit -m "chore: update ComfyUI URL from Colab"
git push
```

### **PASSO 4: Re-executar Workflow**

```bash
# Via gh CLI
gh workflow run full-auto-colab-pipeline.yml

# Ou manualmente no GitHub:
# Actions → full-auto-colab-pipeline → Run workflow
```

---

## 🤖 **Alternativa: Usar URL Fallback**

Se você já tem uma URL do Colab rodando:

```bash
# Atualizar diretamente
python3 scripts/update_comfyui_url.py https://literacy-staff-singer-acknowledge.trycloudflare.com

# Deploy
python3 scripts/auto_deploy.py -m "chore: update ComfyUI URL"
```

---

## 🔧 **Para Automatizar Completamente (Futuro):**

Você precisaria configurar:

1. **Playwright/Selenium** para abrir Colab automaticamente
2. **Webhook** do Colab para notificar GitHub
3. **Gist** atualizado automaticamente pelo notebook

Mas por enquanto, o processo manual (5 min) é mais simples e confiável.

---

## 📊 **Verificar Status:**

```bash
# Diagnóstico
python3 scripts/diagnose_system.py

# Monitor (após atualizar URL)
python3 scripts/monitor_cloudflare.py
```

---

## ✅ **Resultado Esperado:**

Após seguir os passos:
- ✅ ComfyUI rodando no Colab
- ✅ URL atualizada no pipeline
- ✅ Workflow executando com sucesso
- ✅ Score 100% no diagnóstico

---

**Tempo total:** ~5 minutos  
**Próximo passo:** Iniciar o notebook do Colab
