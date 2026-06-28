# 🚀 Guia Completo: Iniciar Colab Automaticamente

> ⚠️ **Legado.** Este documento descreve a automação via Colab + Cloudflare, substituída pelo RunPod Serverless. Veja `RUNPOD_COMFYUI_SETUP.md`.

## 🎯 Objetivo

Fazer o Google Colab iniciar **100% automaticamente** quando o GitHub Actions executar, sem intervenção manual.

---

## 📋 Pré-requisitos

1. ✅ Conta Google
2. ✅ Google Colab notebook criado
3. ✅ GitHub repository configurado
4. ✅ Acesso ao Google Cloud Console

---

## 🔧 Método 1: Google Drive API + Service Account (RECOMENDADO)

### **Passo 1: Criar Service Account no Google Cloud**

1. **Acesse:** https://console.cloud.google.com/

2. **Criar Projeto:**
   ```
   - Clique em "Select a project" → "New Project"
   - Nome: "AI-Film-Colab-Automation"
   - Clique em "Create"
   ```

3. **Ativar APIs:**
   ```
   - Vá em "APIs & Services" → "Enable APIs and Services"
   - Procure e ative:
     ✅ Google Drive API
     ✅ Google Sheets API (opcional)
   ```

4. **Criar Service Account:**
   ```
   - Vá em "IAM & Admin" → "Service Accounts"
   - Clique em "Create Service Account"
   - Nome: "colab-automation"
   - Role: "Editor" (ou "Drive File Access")
   - Clique em "Done"
   ```

5. **Gerar Chave JSON:**
   ```
   - Clique na service account criada
   - Vá em "Keys" → "Add Key" → "Create new key"
   - Tipo: JSON
   - Clique em "Create"
   - Arquivo JSON será baixado automaticamente
   ```

### **Passo 2: Configurar Notebook no Google Drive**

1. **Upload do Notebook:**
   ```bash
   # Upload colab_automated_notebook.ipynb para Google Drive
   # URL: https://drive.google.com/drive/my-drive
   ```

2. **Compartilhar com Service Account:**
   ```
   - Clique com botão direito no notebook
   - "Share" → "Share with people and groups"
   - Cole o email da service account (ex: colab-automation@project-id.iam.gserviceaccount.com)
   - Permissão: "Editor"
   - Desmarque "Notify people"
   - Clique em "Share"
   ```

3. **Copiar ID do Notebook:**
   ```
   - Abra o notebook no Colab
   - URL será: https://colab.research.google.com/drive/XXXXX-NOTEBOOK-ID-XXXXX
   - Copie o ID (parte depois de /drive/)
   ```

### **Passo 3: Configurar GitHub Secrets**

1. **Converter JSON para Base64:**
   ```bash
   # No terminal:
   cat service-account-key.json | base64 > credentials.txt
   
   # Ou online: https://www.base64encode.org/
   ```

2. **Adicionar Secrets no GitHub:**
   ```bash
   # 1. GOOGLE_COLAB_CREDENTIALS (conteúdo base64 do JSON)
   gh secret set GOOGLE_COLAB_CREDENTIALS --body "$(cat credentials.txt)"
   
   # 2. COLAB_NOTEBOOK_ID (ID do notebook)
   gh secret set COLAB_NOTEBOOK_ID --body "XXXXX-SEU-NOTEBOOK-ID-XXXXX"
   ```

### **Passo 4: Configurar Notebook para Auto-Run**

Adicione esta célula NO INÍCIO do notebook:

```python
#@title 🤖 AUTO-START Configuration
#@markdown Esta célula configura o notebook para executar automaticamente

import os
import sys

# Detectar se está sendo executado via API
AUTO_RUN = os.getenv('AUTO_RUN', 'false') == 'true'

if AUTO_RUN:
    print("🤖 Modo AUTO-RUN ativado!")
    print("📡 Executando todas as células automaticamente...")
    
    # Executar todas as células
    from IPython.display import Javascript
    display(Javascript('IPython.notebook.execute_all_cells()'))
else:
    print("👤 Modo MANUAL - Execute as células manualmente")
```

---

## 🔧 Método 2: Webhook + Zapier/Make (ALTERNATIVO)

### **Passo 1: Criar Webhook no Zapier**

1. **Criar conta:** https://zapier.com/

2. **Criar Zap:**
   ```
   - Trigger: "Webhooks by Zapier" → "Catch Hook"
   - Copie a URL do webhook
   ```

3. **Ação: Google Drive**
   ```
   - Action: "Google Drive" → "Find File"
   - File ID: SEU_NOTEBOOK_ID
   - Action: "Open in Colab"
   ```

### **Passo 2: Configurar GitHub Secret**

```bash
gh secret set COLAB_TRIGGER_WEBHOOK --body "https://hooks.zapier.com/hooks/catch/XXXXX/"
```

---

## 🔧 Método 3: GitHub Actions + Playwright (AVANÇADO)

Usar Playwright para automação completa do navegador:
1. Abrir Colab no navegador headless
2. Fazer login com credenciais Google
3. Conectar ao runtime GPU
4. Executar todas as células automaticamente
5. Monitorar execução

### **Passo 1: Configurar Secrets**

```bash
# Email e senha do Google
gh secret set GOOGLE_EMAIL --body "seu_email@gmail.com"
gh secret set GOOGLE_PASSWORD --body "sua_senha"

# ID do notebook (já configurado)
gh secret set COLAB_NOTEBOOK_ID --body "SEU_NOTEBOOK_ID"
```

### **Passo 2: Executar Workflow**

**Arquivo criado:** `.github/workflows/colab-playwright-trigger.yml`

```bash
# Trigger manual via GitHub CLI
gh workflow run "colab-playwright-trigger.yml"

# Ou via interface web
# https://github.com/SEU_USER/SEU_REPO/actions/workflows/colab-playwright-trigger.yml
```

### **Passo 3: Monitorar Execução**

```bash
# Acompanhar workflow
gh run watch

# Ver logs
gh run view --log
```

### **⚠️ Considerações de Segurança**

**Método Playwright:**
- ✅ Funciona 100% automaticamente
- ⚠️ Requer credenciais Google nos secrets
- ⚠️ Pode quebrar se Google mudar UI
- ⚠️ Problemas com 2FA (precisa desativar ou usar App Password)

**Recomendação:**
- Use **Service Account (Método 1)** para produção
- Use **Playwright (Método 3)** para testes/desenvolvimento
- Use **App Password** ao invés de senha real:
  1. Vá em https://myaccount.google.com/apppasswords
  2. Crie app password para "GitHub Actions"
  3. Use esse password no secret `GOOGLE_PASSWORD`

---

## ✅ Validação da Configuração

### **Teste 1: Verificar Service Account**

```bash
# Instalar gcloud CLI
# https://cloud.google.com/sdk/docs/install

# Autenticar com service account
gcloud auth activate-service-account --key-file=service-account-key.json

# Listar arquivos do Drive
gcloud drive files list
```

### **Teste 2: Teste Manual do Agente**

```bash
# Configurar variáveis de ambiente
export GITHUB_TOKEN="seu_github_token"
export GOOGLE_COLAB_CREDENTIALS="$(cat service-account-key.json | base64)"
export COLAB_NOTEBOOK_ID="seu_notebook_id"
export COMFYUI_URL_GIST_ID="seu_gist_id"

# Executar agente
python .github/scripts/colab_automation_agent.py
```

### **Teste 3: Workflow Completo**

```bash
# Trigger workflow manualmente
gh workflow run "full-auto-colab-pipeline.yml"

# Acompanhar execução
gh run watch
```

---

## 🎯 Fluxo Completo Automatizado

```
1. git push origin main
   ↓
2. GitHub Actions inicia
   ↓
3. Agente autentica com Google API (Service Account)
   ↓
4. Agente abre notebook via Drive API
   ↓
5. Notebook detecta AUTO_RUN=true
   ↓
6. Notebook executa todas as células automaticamente
   ↓
7. ComfyUI + Cloudflare iniciam
   ↓
8. Auto-reporter captura URL
   ↓
9. URL enviada para Gist
   ↓
10. GitHub Actions detecta URL
   ↓
11. Pipeline continua automaticamente
   ↓
12. ✅ SUCESSO! 100% Automatizado
```

---

## 🔍 Troubleshooting

### **Erro: "Permission denied"**

**Solução:**
```
1. Verificar se service account tem acesso ao notebook
2. Compartilhar notebook com email da service account
3. Permissão mínima: "Editor"
```

### **Erro: "Notebook not found"**

**Solução:**
```
1. Verificar COLAB_NOTEBOOK_ID está correto
2. Notebook deve estar no Google Drive
3. URL deve ser: https://colab.research.google.com/drive/ID
```

### **Erro: "API not enabled"**

**Solução:**
```
1. Ativar Google Drive API no projeto
2. Ativar Google Sheets API (opcional)
3. Aguardar 1-2 minutos para propagação
```

---

## 📊 Comparação de Métodos

| Método | Complexidade | Confiabilidade | Custo | Segurança | Recomendado |
|--------|--------------|----------------|-------|-----------|-------------|
| **1. Service Account** | Média | ⭐⭐⭐⭐⭐ | Grátis | ⭐⭐⭐⭐⭐ | ✅ **PRODUÇÃO** |
| **2. Webhook + Zapier** | Baixa | ⭐⭐⭐⭐ | Grátis (limite) | ⭐⭐⭐⭐ | ⚠️ OK |
| **3. Playwright** | Alta | ⭐⭐⭐⭐ | Grátis | ⭐⭐⭐ | 🧪 **TESTES** |

### **Quando Usar Cada Método:**

**Service Account (Método 1):**
- ✅ Produção e uso contínuo
- ✅ Máxima segurança (sem credenciais de usuário)
- ✅ Não quebra com mudanças de UI
- ✅ Suporta 2FA sem problemas
- ⚠️ Requer configuração inicial no Google Cloud

**Webhook + Zapier (Método 2):**
- ✅ Setup rápido e fácil
- ✅ Interface visual (no-code)
- ⚠️ Limite de execuções no plano grátis
- ⚠️ Depende de serviço terceiro

**Playwright (Método 3):**
- ✅ Funciona imediatamente (sem config complexa)
- ✅ Útil para testes e desenvolvimento
- ✅ Controle total do processo
- ⚠️ Requer credenciais Google nos secrets
- ⚠️ Pode quebrar se Google mudar UI
- ⚠️ Problemas com 2FA (usar App Password)

---

## 🚀 Próximos Passos

1. **Escolher Método:**
   - ✅ Recomendado: Service Account (Método 1)

2. **Configurar Secrets:**
   ```bash
   gh secret set GOOGLE_COLAB_CREDENTIALS --body "BASE64_JSON"
   gh secret set COLAB_NOTEBOOK_ID --body "NOTEBOOK_ID"
   ```

3. **Testar:**
   ```bash
   gh workflow run "full-auto-colab-pipeline.yml"
   gh run watch
   ```

4. **Validar:**
   - Verificar logs do workflow
   - Confirmar que Colab iniciou
   - Verificar URL no Gist

---

## 📞 Suporte

**Documentação Oficial:**
- Google Drive API: https://developers.google.com/drive/api/guides/about-sdk
- Service Accounts: https://cloud.google.com/iam/docs/service-accounts
- Colab: https://colab.research.google.com/

**Comandos Úteis:**
```bash
# Ver secrets configurados
gh secret list

# Testar workflow
gh workflow run "full-auto-colab-pipeline.yml"

# Ver logs
gh run view --log
```

---

## ✅ Checklist Final

- [ ] Service Account criada
- [ ] APIs ativadas (Drive API)
- [ ] Chave JSON baixada
- [ ] Notebook compartilhado com service account
- [ ] GOOGLE_COLAB_CREDENTIALS configurado
- [ ] COLAB_NOTEBOOK_ID configurado
- [ ] Célula AUTO-START adicionada ao notebook
- [ ] Teste manual executado
- [ ] Workflow testado
- [ ] ✅ 100% Automatizado!

---

**Data:** 2025-10-11  
**Status:** Guia Completo  
**Próximo:** Configurar Service Account  
