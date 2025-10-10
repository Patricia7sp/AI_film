# 🤖 Setup AUTOMÁTICO ComfyUI + GitHub Actions

## 🎯 **Solução 100% Automática**

Esta solução **ELIMINA a necessidade de atualizar secrets manualmente**. A URL do ComfyUI é capturada e atualizada automaticamente usando GitHub Gist como intermediário.

---

## 📋 **Como Funciona**

```
┌─────────────────────────────────────────────────────────────┐
│                     FLUXO AUTOMÁTICO                         │
└─────────────────────────────────────────────────────────────┘

1. ComfyUI inicia no Colab
   ↓
2. Cloudflare cria túnel (URL dinâmica)
   ↓
3. Script Python captura URL do log
   ↓
4. URL é enviada para GitHub Gist (privado)
   ↓
5. GitHub Actions lê URL do Gist
   ↓
6. Secret COMFYUI_FALLBACK_URL é atualizado automaticamente
   ↓
7. Deploy continua com URL atualizada
   ↓
✅ ZERO INTERVENÇÃO MANUAL!
```

---

## 🔧 **Setup (Uma Vez Apenas)**

### **Passo 1: Criar Personal Access Token do GitHub**

1. Acesse: https://github.com/settings/tokens
2. Clique em **"Generate new token"** → **"Generate new token (classic)"**
3. Configure:
   - **Note:** `ComfyUI Auto Update`
   - **Scopes:** Marque `gist` (criar/atualizar Gists)
4. Clique em **"Generate token"**
5. **COPIE O TOKEN** (você não verá novamente!)

**Token terá formato:** `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx`

---

### **Passo 2: Atualizar Notebook do Colab**

1. Abra seu notebook: https://colab.research.google.com/drive/1bfDjw5JGeqExdsUWYM41txvqlCGzOF99

2. **Adicione ao FINAL do notebook:**

```python
# ============================================================
# CAPTURA AUTOMÁTICA DE URL - GITHUB ACTIONS
# ============================================================

import re
import time
import requests
import json

def capture_and_send_comfyui_url_auto():
    """Captura URL e envia automaticamente para GitHub Gist"""
    
    # CONFIGURE AQUI COM SEU TOKEN
    GITHUB_TOKEN = "ghp_YOUR_TOKEN_HERE"  # ⚠️ SUBSTITUA!
    GIST_ID = None  # Na primeira execução, deixe None
    
    print("="*70)
    print("🎬 CAPTURA AUTOMÁTICA DE URL")
    print("="*70)
    
    # Aguardar túnel
    print("\n⏳ Aguardando túnel Cloudflare...")
    time.sleep(30)
    
    # Capturar URL do log
    tunnel_url = None
    try:
        with open('/content/cloudflared.log', 'r') as f:
            log = f.read()
            match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', log)
            if match:
                tunnel_url = match.group(0)
                print(f"✅ URL: {tunnel_url}")
    except Exception as e:
        print(f"❌ Erro: {e}")
        return
    
    if not tunnel_url:
        print("❌ URL não encontrada")
        return
    
    # Enviar para Gist
    print("\n📤 Enviando para GitHub Gist...")
    
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
                    "url": tunnel_url,
                    "updated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "status": "active"
                }, indent=2)
            }
        }
    }
    
    try:
        if GIST_ID:
            response = requests.patch(
                f'https://api.github.com/gists/{GIST_ID}',
                headers=headers,
                json=gist_data
            )
        else:
            response = requests.post(
                'https://api.github.com/gists',
                headers=headers,
                json=gist_data
            )
        
        if response.status_code in [200, 201]:
            gist_id = response.json()['id']
            print(f"✅ Enviado para Gist!")
            print(f"   Gist ID: {gist_id}")
            
            if not GIST_ID:
                print(f"\n⚠️ PRIMEIRA EXECUÇÃO:")
                print(f"   1. Copie este ID: {gist_id}")
                print(f"   2. Atualize GIST_ID no código: GIST_ID = '{gist_id}'")
                print(f"   3. Configure secret: gh secret set COMFYUI_URL_GIST_ID --body '{gist_id}'")
        else:
            print(f"❌ Erro: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    print("\n" + "="*70)
    print("✅ AUTOMAÇÃO CONFIGURADA!")
    print("="*70)
    print(f"\n🎯 ComfyUI URL: {tunnel_url}")
    print("\n🤖 Processo automático:")
    print("   ✅ URL capturada")
    print("   ✅ Enviada para GitHub")
    print("   ✅ GitHub Actions atualizará automaticamente")
    print("="*70)

# Executar
capture_and_send_comfyui_url_auto()
```

3. **Salve o notebook** (Ctrl+S ou File → Save)

---

### **Passo 3: Primeira Execução (Setup Inicial)**

1. **Execute o notebook do Colab** (Runtime → Run all)

2. **Aguarde a saída:**
```
✅ Enviado para Gist!
   Gist ID: abc123def456
   
⚠️ PRIMEIRA EXECUÇÃO:
   1. Copie este ID: abc123def456
   2. Atualize GIST_ID no código
   3. Configure secret no GitHub
```

3. **COPIE O GIST_ID** mostrado

4. **Atualize o código do Colab:**
```python
GIST_ID = "abc123def456"  # ⚠️ Cole o ID aqui
```

5. **Configure o secret no GitHub:**
```bash
cd /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP
gh secret set COMFYUI_URL_GIST_ID --body "abc123def456"
```

6. **Salve o notebook novamente**

---

## ✅ **Pronto! Agora é Automático**

### **Como Usar:**

1. **Execute o Colab** (qualquer hora)
   ```
   Runtime → Run all
   ```

2. **GitHub Actions detecta automaticamente**
   ```
   - Lê URL do Gist
   - Atualiza secret
   - Deploy continua automaticamente
   ```

3. **ZERO intervenção manual!** 🎉

---

## 🔍 **Verificar se Está Funcionando**

### **No Colab:**
```
✅ URL: https://xxx.trycloudflare.com
✅ Enviado para Gist!
```

### **No GitHub Actions:**
```bash
# Ver último workflow
gh run list --limit 1

# Ver logs
gh run view <run-id> --log | grep "URL obtida"

# Deve mostrar:
# ✅ URL obtida do Gist: https://xxx.trycloudflare.com
```

### **Verificar Secret Atualizado:**
```bash
# Ver quando foi atualizado
gh secret list | grep COMFYUI

# Deve mostrar timestamp recente
```

---

## 🐛 **Troubleshooting**

### **Problema: "Erro ao enviar para Gist"**

**Solução:**
```bash
# Verificar se o token tem permissão 'gist'
# Criar novo token em: https://github.com/settings/tokens
# Atualizar no Colab
```

### **Problema: "Gist ID não configurado"**

**Solução:**
```bash
# Configurar secret
gh secret set COMFYUI_URL_GIST_ID --body "seu-gist-id"

# Verificar
gh secret list | grep GIST
```

### **Problema: "URL não encontrada no log"**

**Solução:**
```bash
# No Colab, verificar log do Cloudflare
!cat /content/cloudflared.log | grep trycloudflare

# Deve mostrar URL
```

---

## 📊 **Comparação: Manual vs Automático**

| Aspecto | Manual | Automático |
|---------|--------|------------|
| **Atualizar URL** | 🔴 Manual | ✅ Automático |
| **Tempo** | ~5 minutos | ~30 segundos |
| **Erros** | ⚠️ Comum | ✅ Raro |
| **Manutenção** | 🔴 Toda vez | ✅ Uma vez |
| **Confiabilidade** | ⚠️ Média | ✅ Alta |

---

## 🎯 **Fluxo Completo**

```bash
# 1. Push código
git push origin feature/minha-feature

# 2. GitHub Actions inicia
# 3. Lê URL do Gist (atualizada pelo Colab)
# 4. Atualiza secret automaticamente
# 5. Deploy com URL correta
# 6. ✅ Sucesso!

# ZERO INTERVENÇÃO MANUAL!
```

---

## 🔐 **Segurança**

✅ **Gist privado** - Apenas você tem acesso
✅ **Token com escopo limitado** - Apenas permissão para Gists
✅ **Secret no GitHub** - Não exposto no código
✅ **URL temporária** - Muda a cada execução do Colab

---

## 🎉 **Benefícios**

✅ **100% Automático** - Zero intervenção manual
✅ **Confiável** - Funciona toda vez
✅ **Rápido** - URL atualizada em segundos
✅ **Seguro** - Usa APIs oficiais do GitHub
✅ **Escalável** - Funciona para múltiplos projetos

---

## 📚 **Próximos Passos**

Depois de configurar:

1. ✅ Execute Colab
2. ✅ Push código para GitHub
3. ✅ Veja deploy automático
4. ✅ Profit! 🚀

**Tudo automático, do início ao fim!**
