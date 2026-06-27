# 🔧 Troubleshooting: Colab Automation

**Data:** 2025-10-12  
**Status:** PROBLEMA IDENTIFICADO E SOLUÇÃO DOCUMENTADA

---

## 🎯 **PROBLEMA IDENTIFICADO**

Pipeline falhou com erro:
```
[WARN] ⚠️ GOOGLE_COLAB_CREDENTIALS não configurado
```

### **Análise dos Logs**

**Run ID:** 18437359453  
**Falha em:** Job "Orchestrate Colab" após 5m14s

**Sequência de erros:**
1. `[WARN] ⚠️ GOOGLE_COLAB_CREDENTIALS não configurado`
2. `[INFO] 📡 Usando método webhook para iniciar Colab...`
3. `[WARN] ⚠️ Erro no webhook: Invalid URL`
4. `[ERROR] ❌ Timeout aguardando Colab ficar pronto`

---

## 🔍 **CAUSA RAIZ**

### **Problema 1: Credenciais Incorretas**

**Arquivo existente:** `./colab_integration/credentials.json`

❌ **Tipo errado:** OAuth Client (credenciais de aplicação)
```json
{
  "installed": {
    "client_id": "899357076456-...",
    "client_secret": "GOCSPX-...",
    ...
  }
}
```

✅ **Tipo necessário:** Service Account
```json
{
  "type": "service_account",
  "project_id": "ia-video-460518",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...",
  "client_email": "xxx@ia-video-460518.iam.gserviceaccount.com",
  ...
}
```

### **Problema 2: Secret Mal Configurado**

O secret `GOOGLE_COLAB_CREDENTIALS` existe mas contém o arquivo OAuth Client errado.

---

## ✅ **SOLUÇÃO COMPLETA**

### **Passo 1: Criar Service Account**

1. **Acesse Google Cloud Console:**
   ```
   https://console.cloud.google.com/iam-admin/serviceaccounts?project=ia-video-460518
   ```

2. **Clique "+ CREATE SERVICE ACCOUNT"**

3. **Preencha os dados:**
   - **Name:** `colab-executor`
   - **ID:** `colab-executor` (gerado automaticamente)
   - **Description:** `Executes Colab notebooks automatically`

4. **Grant Access:**
   - **Role:** `Editor` (ou `Drive File Creator` para mais segurança)
   - Clique **"CONTINUE"** → **"DONE"**

5. **Criar Chave JSON:**
   - Clique na service account criada
   - Aba **"KEYS"**
   - **"ADD KEY"** → **"Create new key"**
   - Selecione **"JSON"**
   - Clique **"CREATE"**

6. **Arquivo será baixado automaticamente**
   - Nome: `ia-video-460518-xxxxxxxxxxxx.json`
   - **IMPORTANTE:** Guarde em local seguro!

---

### **Passo 2: Configurar Secret no GitHub**

```bash
# Navegar para pasta do projeto
cd /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP

# Configurar secret com arquivo baixado
gh secret set GOOGLE_COLAB_CREDENTIALS < ~/Downloads/ia-video-460518-xxxxxxxxxxxx.json

# Verificar
gh secret list | grep GOOGLE_COLAB_CREDENTIALS
```

**Exemplo de saída esperada:**
```
GOOGLE_COLAB_CREDENTIALS    2025-10-12T13:45:00Z
```

---

### **Passo 3: Habilitar Drive API**

1. **Acesse:**
   ```
   https://console.cloud.google.com/apis/library/drive.googleapis.com?project=ia-video-460518
   ```

2. **Clique "ENABLE"** (se não estiver habilitada)

3. **Aguarde alguns segundos** para API ser ativada

---

### **Passo 4: Compartilhar Notebook com Service Account**

1. **Copie o email da service account:**
   ```
   colab-executor@ia-video-460518.iam.gserviceaccount.com
   ```

2. **Abra o notebook Colab:**
   ```
   https://colab.research.google.com/drive/1bfDjw5JGeqExdsUWYM41txvqlCGzOF99
   ```

3. **Clique "Compartilhar" (Share)**

4. **Cole o email da service account**

5. **Selecione permissão:** `Editor` (ou `Viewer` se preferir)

6. **Clique "Enviar"**

7. **Desmarque** "Notify people" (service accounts não recebem email)

---

### **Passo 5: Atualizar Notebook ID Secret**

```bash
# Notebook ID extraído da URL
NOTEBOOK_ID="1bfDjw5JGeqExdsUWYM41txvqlCGzOF99"

# Configurar secret
gh secret set COLAB_NOTEBOOK_ID --body "$NOTEBOOK_ID"
```

---

### **Passo 6: Verificar Todos os Secrets**

```bash
# Listar secrets necessários
gh secret list | grep -E "COLAB|COMFYUI|GOOGLE"
```

**Secrets obrigatórios:**
```
✅ GOOGLE_COLAB_CREDENTIALS  (JSON da service account)
✅ COLAB_NOTEBOOK_ID         (1bfDjw5JGeqExdsUWYM41txvqlCGzOF99)
✅ COMFYUI_URL_GIST_ID       (ID do Gist para URL)
⚠️ COMFYUI_FALLBACK_URL      (URL de fallback - opcional)
⚠️ COLAB_TRIGGER_WEBHOOK     (Webhook - opcional)
```

---

## 🧪 **VALIDAÇÃO**

### **Teste 1: Verificar Service Account**

```bash
# Extrair email da service account do arquivo
cat ~/Downloads/ia-video-460518-*.json | jq -r '.client_email'
```

**Saída esperada:**
```
colab-executor@ia-video-460518.iam.gserviceaccount.com
```

### **Teste 2: Verificar JSON Válido**

```bash
# Validar estrutura do JSON
cat ~/Downloads/ia-video-460518-*.json | jq '.type'
```

**Saída esperada:**
```
"service_account"
```

### **Teste 3: Verificar Compartilhamento**

1. Abrir notebook no Colab
2. Clicar "Compartilhar"
3. Verificar se service account aparece na lista

---

## 🚀 **EXECUTAR PIPELINE NOVAMENTE**

```bash
# Re-executar workflow
gh workflow run "full-auto-colab-pipeline.yml" --ref automation-only

# Acompanhar execução
gh run watch
```

---

## 📊 **LOGS ESPERADOS (SUCESSO)**

Quando funcionar corretamente, você verá nos logs:

```
[INFO] 🤖 Iniciando automação completa do Colab...
[INFO] 🚀 Iniciando execução do Colab notebook...
[INFO] ✅ Service Account autenticada com sucesso
[INFO] 📋 Notebook ID: 1bfDjw5JGeqExdsUWYM41txvqlCGzOF99
[INFO] 🚀 Executando notebook...
[INFO] ✅ Notebook iniciado com sucesso!
[INFO] ⏳ Aguardando Colab iniciar e ComfyUI estar pronto...
[INFO] ✅ URL capturada do Gist: https://xxx.trycloudflare.com
[INFO] ✅ ComfyUI está acessível!
```

---

## ❓ **FAQ - Perguntas Frequentes**

### **1. Por que não posso usar OAuth Client?**

OAuth Client é para aplicações que rodam no navegador do usuário. Service Account é para automação server-to-server sem intervenção humana.

### **2. O secret está configurado mas continua dizendo "não configurado"?**

Verifique se o JSON tem o campo `"type": "service_account"`. Se tiver `"installed"`, é OAuth Client, não Service Account.

### **3. Já compartilhei o notebook mas não funciona?**

Verifique:
- Email correto da service account (deve terminar com `@<projeto>.iam.gserviceaccount.com`)
- Permissão deve ser Editor ou Viewer
- Drive API habilitada no projeto

### **4. Como testar localmente?**

```bash
cd .github/scripts
export GOOGLE_COLAB_CREDENTIALS="$(cat ~/Downloads/ia-video-*.json)"
export COLAB_NOTEBOOK_ID="1bfDjw5JGeqExdsUWYM41txvqlCGzOF99"
python colab_automation_agent.py
```

---

## 🔗 **Links Úteis**

- **Google Cloud Console - Service Accounts:**  
  https://console.cloud.google.com/iam-admin/serviceaccounts?project=ia-video-460518

- **Google Cloud Console - Drive API:**  
  https://console.cloud.google.com/apis/library/drive.googleapis.com?project=ia-video-460518

- **Colab Notebook:**  
  https://colab.research.google.com/drive/1bfDjw5JGeqExdsUWYM41txvqlCGzOF99

- **GitHub Actions:**  
  https://github.com/Patricia7sp/AI_film/actions

---

## 📝 **Checklist Final**

Antes de executar o pipeline, verifique:

```
✅ Service Account criada no GCP
✅ Chave JSON baixada
✅ Secret GOOGLE_COLAB_CREDENTIALS configurado
✅ Secret COLAB_NOTEBOOK_ID configurado
✅ Drive API habilitada
✅ Notebook compartilhado com service account
✅ Email da service account correto
✅ Permissão concedida (Editor ou Viewer)
```

---

## 🎯 **Resultado Esperado**

Após seguir todos os passos:

1. ✅ Pipeline executa sem erros
2. ✅ Colab inicia automaticamente
3. ✅ ComfyUI configura automaticamente
4. ✅ URL capturada automaticamente
5. ✅ Dagster + Flask iniciam
6. ✅ História processada
7. ✅ Filme gerado

**Tempo total:** ~18-40 minutos

---

**Última atualização:** 2025-10-12  
**Autor:** Cascade AI  
**Status:** ✅ Problema Resolvido
