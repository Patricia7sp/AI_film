# 🔐 **Guia de Secrets - GitHub → Colab**

## **✅ Secrets que Você JÁ TEM no GitHub**

Baseado na sua imagem, você já tem estas secrets configuradas:

| Secret no GitHub | Descrição | Precisa no Colab? |
|------------------|-----------|-------------------|
| `COLAB_NOTEBOOK_ID` | ID do notebook Colab | ❌ Não |
| `COLAB_TRIGGER_WEBHOOK` | Webhook para trigger | ❌ Não |
| `COMFYUI_FALLBACK_URL` | URL fallback | ❌ Não |
| **`COMFYUI_URL_GIST_ID`** | **ID do Gist** | ✅ **SIM!** |
| `COMFYUI_WEBHOOK_URL` | Webhook do ComfyUI | ❌ Não |

---

## **🎯 O Que Você Precisa no Colab**

### **3 Variáveis Necessárias:**

1. ✅ **`GITHUB_TOKEN`** - Token de acesso (você vai criar agora)
2. ✅ **`GITHUB_REPO`** - Repositório (já sabemos: `Patricia7sp/AI_film`)
3. ✅ **`COMFYUI_URL_GIST_ID`** - ID do Gist (você JÁ TEM no GitHub!)

---

## **📝 PASSO 1: Criar GitHub Token**

### **Onde:**
1. GitHub → Seu avatar (canto superior direito) → **Settings**
2. Rolar até o final → **Developer settings**
3. **Personal access tokens** → **Tokens (classic)**
4. **Generate new token** → **Generate new token (classic)**

### **Configurar:**
- **Note:** `Colab Automation Token`
- **Expiration:** Escolha (recomendo: `No expiration`)
- **Select scopes:**
  - ✅ `workflow` (disparar GitHub Actions)
  - ✅ `gist` (ler/escrever Gists)

### **Gerar e Copiar:**
5. Clicar **Generate token**
6. **COPIAR O TOKEN** (começa com `ghp_...`)
7. ⚠️ **Guarde bem! Só aparece 1 vez!**

---

## **📋 PASSO 2: Obter o GIST_ID**

Você JÁ TEM a secret `COMFYUI_URL_GIST_ID` criada no GitHub!

### **Opção A: Ver o Valor no GitHub** (Recomendado)

1. Vá em: **Settings → Secrets and variables → Actions**
2. Clique no **ícone de lápis** ao lado de `COMFYUI_URL_GIST_ID`
3. **Copie o valor** (é um ID tipo: `abc123def456`)

### **Opção B: Ver o Gist Diretamente**

1. Vá em: https://gist.github.com/Patricia7sp
2. Procure por: "ComfyUI URL"
3. O ID está na URL: `https://gist.github.com/Patricia7sp/[ESTE_É_O_ID]`

---

## **🚀 PASSO 3: Configurar no Colab**

### **No seu notebook Colab, adicione ANTES do código principal:**

```python
import os

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DE SECRETS - COLE SEUS VALORES AQUI
# ════════════════════════════════════════════════════════════════════════════

# 1. Token do GitHub (que você acabou de criar)
os.environ["GITHUB_TOKEN"] = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # ← COLE SEU TOKEN AQUI

# 2. ID do Gist (copie da secret COMFYUI_URL_GIST_ID)
os.environ["COMFYUI_URL_GIST_ID"] = "abc123def456"  # ← COLE O ID DO GIST AQUI

# 3. Repositório (já está correto)
# Não precisa definir, usaremos direto no código

print("✅ Secrets configuradas!")
print(f"📝 Gist ID: {os.environ['COMFYUI_URL_GIST_ID']}")
print(f"🔑 Token: {'*' * 30}")
```

---

## **💡 Alternativa: Usar Google Colab Secrets** (Mais Seguro)

### **No Colab:**

1. Clique no **ícone de chave 🔑** (Secrets) na barra lateral esquerda
2. Adicione 2 secrets:

   | Name | Value |
   |------|-------|
   | `GITHUB_TOKEN` | `ghp_seu_token_completo` |
   | `COMFYUI_URL_GIST_ID` | `id_do_seu_gist` |

3. No código, acesse assim:

```python
from google.colab import userdata

# Ler secrets do Colab
GITHUB_TOKEN = userdata.get('GITHUB_TOKEN')
GIST_ID = userdata.get('COMFYUI_URL_GIST_ID')
GITHUB_REPO = "Patricia7sp/AI_film"

print("✅ Secrets carregadas do Google Colab Secrets!")
```

---

## **🎯 Configuração Completa no colab_complete_setup.py**

### **Localize esta seção no código:**

```python
# ════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO - AJUSTE AQUI!
# ════════════════════════════════════════════════════════════════════════════

# Timeouts e configurações
TIMEOUT_MINUTES = 30  # Deixe 30 para economia

# GitHub configurações
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # ← Já vai funcionar se você definiu acima
GITHUB_REPO = "Patricia7sp/AI_film"       # ← Já está correto!

# Gist configurações
GIST_ID = os.getenv("COMFYUI_URL_GIST_ID")  # ← Já vai funcionar se você definiu acima

# ComfyUI URL (será preenchido automaticamente depois)
COMFYUI_URL = os.getenv("COMFYUI_URL")  # ← Deixe assim
```

**Não precisa mudar nada aqui!** As variáveis já vão estar definidas com o `os.environ` que você fez antes.

---

## **✅ Checklist Final**

- [ ] Token do GitHub criado com scopes `workflow` e `gist`
- [ ] Token copiado (começa com `ghp_`)
- [ ] GIST_ID obtido da secret `COMFYUI_URL_GIST_ID`
- [ ] Ambos definidos no Colab (via `os.environ` ou Colab Secrets)
- [ ] Testado: executar célula → sem erros

---

## **🐛 Troubleshooting**

### **"GITHUB_TOKEN não configurado"**
- Verifique se definiu `os.environ["GITHUB_TOKEN"]`
- Ou se adicionou no Colab Secrets

### **"GIST_ID não configurado"**
- Copie o valor de `COMFYUI_URL_GIST_ID` do GitHub
- Defina `os.environ["COMFYUI_URL_GIST_ID"]`

### **"GitHub Actions não disparou"**
- Verifique se token tem scope `workflow`
- Confirme que repositório está correto
- Teste manualmente: `manager.trigger_github_actions()`

---

## **📌 Resumo Ultra-Rápido**

```python
# No Colab, adicione ANTES do código principal:

import os

# Seus valores:
os.environ["GITHUB_TOKEN"] = "ghp_SEU_TOKEN_AQUI"
os.environ["COMFYUI_URL_GIST_ID"] = "ID_DO_GIST_AQUI"

# Agora pode executar o resto do código!
```

---

**Pronto! Com isso configurado, o sistema vai disparar o GitHub Actions automaticamente! 🚀**
