# 🎮 Setup ComfyUI com GPU (Colab) + CI/CD Automático

> ⚠️ **Legado.** Este documento descreve a automação via Colab + Cloudflare, substituída pelo RunPod Serverless. Veja `RUNPOD_COMFYUI_SETUP.md`.

## 🎯 **Arquitetura Correta**

```
┌─────────────────────────────────────────────────────────────┐
│                     FLUXO COMPLETO                          │
└─────────────────────────────────────────────────────────────┘

1. COLAB (GPU Grátis)
   └─> ComfyUI rodando com modelos pesados
   └─> Cloudflare Tunnel cria URL pública
   └─> URL enviada para GitHub Gist automaticamente

2. GITHUB ACTIONS (Orquestrador)
   └─> Lê URL do Gist
   └─> Atualiza configurações
   └─> Executa testes
   └─> Deploy no Kubernetes
   └─> ✅ TUDO AUTOMÁTICO!
```

---

## 🚀 **Setup Inicial (Uma Vez)**

### **Passo 1: Criar Personal Access Token**

```bash
# 1. Acesse: https://github.com/settings/tokens
# 2. "Generate new token (classic)"
# 3. Nome: "ComfyUI Auto Update"
# 4. Marque apenas: "gist"
# 5. Generate token
# 6. COPIE: ghp_xxxxxxxxxxxx
```

### **Passo 2: Atualizar Notebook do Colab**

**Notebook:** https://colab.research.google.com/drive/1bfDjw5JGeqExdsUWYM41txvqlCGzOF99

**Cole no FINAL do notebook:**

```python
# ============================================================
# 🤖 AUTO-UPDATE COMFYUI URL PARA GITHUB
# ============================================================

import re, time, requests, json, subprocess

def auto_update_comfyui_url():
    """Captura URL do ComfyUI e envia para GitHub Gist automaticamente"""

    # ⚠️ COLE SEU TOKEN AQUI!
    GITHUB_TOKEN = "ghp_SEU_TOKEN_AQUI"

    # Deixe None na primeira execução
    GIST_ID = None  # Depois atualize com o ID gerado

    print("🎬 Capturando URL do ComfyUI...")
    time.sleep(30)  # Aguardar túnel estabilizar

    # Capturar URL do log do Cloudflare
    try:
        with open('/content/cloudflared.log', 'r') as f:
            log_content = f.read()
            match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', log_content)
            url = match.group(0) if match else None
    except Exception as e:
        print(f"❌ Erro ao ler log: {e}")
        return

    if not url:
        print("❌ URL não encontrada no log")
        return

    print(f"✅ URL capturada: {url}")

    # Criar/Atualizar Gist
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }

    gist_data = {
        "description": "ComfyUI URL - AI Film Pipeline",
        "public": False,
        "files": {
            "comfyui_url.json": {
                "content": json.dumps({
                    "url": url,
                    "updated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "status": "active"
                }, indent=2)
            }
        }
    }

    if GIST_ID:
        # Atualizar Gist existente
        response = requests.patch(
            f'https://api.github.com/gists/{GIST_ID}',
            headers=headers,
            json=gist_data
        )
    else:
        # Criar novo Gist
        response = requests.post(
            'https://api.github.com/gists',
            headers=headers,
            json=gist_data
        )

    if response.status_code in [200, 201]:
        gist_id = response.json()['id']
        print(f"✅ URL enviada para Gist!")
        print(f"🔗 Gist: https://gist.github.com/{gist_id}")

        if not GIST_ID:
            print(f"\n⚠️ IMPORTANTE - FAÇA ISSO AGORA:")
            print(f"1. Atualize GIST_ID = '{gist_id}' neste código")
            print(f"2. Execute no terminal:")
            print(f"   gh secret set COMFYUI_URL_GIST_ID --body '{gist_id}'")
    else:
        print(f"❌ Erro ao enviar para Gist: {response.status_code}")
        print(response.text)

# Executar
auto_update_comfyui_url()
```

### **Passo 3: Primeira Execução**

1. **Execute o notebook Colab** (Runtime → Run all)
2. **Aguarde ComfyUI iniciar** (~2-3 minutos)
3. **Copie o Gist ID** da saída
4. **Configure o secret:**

```bash
cd /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP
gh secret set COMFYUI_URL_GIST_ID --body "SEU_GIST_ID_AQUI"
```

5. **Atualize o notebook:**
   - Substitua `GIST_ID = None` por `GIST_ID = "seu-gist-id"`
   - Salve o notebook

---

## ✅ **Pronto! Agora é Automático**

### **Workflow Completo:**

```
1. 🚀 Push código para GitHub
   ↓
2. 🎮 Colab detecta e atualiza URL no Gist (automático)
   ↓
3. 🤖 GitHub Actions lê URL do Gist
   ↓
4. ⚙️ Atualiza configurações automaticamente
   ↓
5. 🧪 Executa testes com ComfyUI
   ↓
6. 🚢 Deploy no Kubernetes
   ↓
7. ✅ Sistema funcionando!
```

---

## 🔄 **Uso Diário**

### **Opção 1: Totalmente Automático (Recomendado)**

```bash
# 1. Mantenha Colab rodando (GPU grátis por ~12h)
# 2. Faça commits normalmente
git add .
git commit -m "feat: new feature"
git push

# 3. GitHub Actions faz o resto! ✨
```

### **Opção 2: URL Manual (Backup)**

Se o Gist não estiver configurado:

```bash
# 1. Execute Colab e copie a URL
# 2. Configure manualmente:
gh secret set COMFYUI_FALLBACK_URL --body "https://sua-url.trycloudflare.com"

# 3. Push
git push
```

---

## 📊 **Monitorar Pipeline**

```bash
# Ver workflows em execução
gh run list --limit 5

# Ver detalhes do último run
gh run view --log

# Abrir no navegador
open https://github.com/Patricia7sp/AI_film/actions
```

---

## 🎯 **Fluxo dos Jobs**

```yaml
Job 1: get-comfyui-url
  ├─> Tenta ler URL manual (COMFYUI_FALLBACK_URL)
  ├─> Se não, lê do Gist (COMFYUI_URL_GIST_ID)
  └─> Verifica conectividade

Job 2: update-config
  └─> Atualiza .env com URL

Job 3: test-with-comfyui
  └─> Testa integração com ComfyUI

Job 4: deploy-kubernetes (só em main)
  ├─> Atualiza secret do K8s
  └─> Deploy aplicação

Job 5: notify
  └─> Envia notificação
```

---

## 🐛 **Troubleshooting**

### **Erro: "URL não disponível"**

```bash
# Verificar se Colab está rodando
# Verificar se Gist foi criado
gh gist list

# Verificar se secret está configurado
gh secret list | grep COMFYUI

# Testar URL manualmente
curl https://sua-url.trycloudflare.com
```

### **Erro: "ComfyUI não está respondendo"**

```bash
# No Colab, verificar logs:
!tail -50 /content/ComfyUI/comfyui.log
!tail -50 /content/cloudflared.log

# Verificar se processo está rodando
!ps aux | grep python
!ps aux | grep cloudflared
```

### **Erro: "Gist não atualiza"**

```bash
# Verificar se token está correto
# Token precisa ter permissão "gist"
# Regenerar token se necessário
```

---

## 💡 **Vantagens desta Arquitetura**

✅ **GPU Grátis:** Colab oferece GPU T4 gratuitamente
✅ **Zero Config:** Após setup inicial, tudo automático
✅ **Robusto:** Fallback manual se necessário
✅ **Flexível:** Pode trocar URL sem reconfigurar tudo
✅ **Escalável:** Adicione mais Colabs se necessário
✅ **CI/CD:** Totalmente integrado com GitHub Actions

---

## 🎬 **Demo Rápido**

```bash
# Setup uma vez (5 minutos)
1. Criar token GitHub
2. Atualizar notebook Colab
3. Executar Colab
4. Configurar secret COMFYUI_URL_GIST_ID

# Depois disso...
git add .
git commit -m "test"
git push

# GitHub Actions automaticamente:
✅ Lê URL do Colab
✅ Atualiza configs
✅ Testa pipeline
✅ Deploy
```

**Tempo total:** < 10 minutos para deploy completo!

---

## 📚 **Documentos Relacionados**

- [AUTOMATIC_COMFYUI_SETUP.md](./AUTOMATIC_COMFYUI_SETUP.md) - Setup detalhado
- [.github/workflows/full-auto-deploy.yml](./.github/workflows/full-auto-deploy.yml) - Workflow completo
- [.github/scripts/auto_update_comfyui_url.py](./.github/scripts/auto_update_comfyui_url.py) - Script Python

---

**🎉 Parabéns! Agora você tem um CI/CD totalmente automático com GPU grátis!**
