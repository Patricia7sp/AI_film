# 🔐 Como Adicionar GEMINI_API_KEY no GitHub Secrets

## 📋 Método 1: Via Interface Web (Recomendado - Mais Seguro)

### **Passo a Passo:**

1. **Acesse o repositório:**
   ```
   https://github.com/Patricia7sp/AI_film
   ```

2. **Vá para Settings:**
   - Clique em **Settings** (no menu superior do repositório)

3. **Acesse Secrets and variables:**
   - No menu lateral esquerdo, clique em **Secrets and variables**
   - Depois clique em **Actions**

4. **Adicione o novo secret:**
   - Clique no botão **New repository secret**

5. **Preencha os campos:**
   ```
   Name: GEMINI_API_KEY
   Secret: AIzaSyD6L3PQI5MSmiQvosOrhcQllU4_O3UplP4
   ```

6. **Salve:**
   - Clique em **Add secret**

7. **✅ Pronto!**
   - O secret está configurado e será usado nos workflows

---

## 📋 Método 2: Via GitHub CLI (Alternativo)

### **Pré-requisitos:**
```bash
# Instalar GitHub CLI (se não tiver)
brew install gh  # macOS
# ou
# sudo apt install gh  # Linux
```

### **Autenticar:**
```bash
gh auth login
```

### **Adicionar o secret:**
```bash
gh secret set GEMINI_API_KEY \
  --repo Patricia7sp/AI_film \
  --body "AIzaSyD6L3PQI5MSmiQvosOrhcQllU4_O3UplP4"
```

### **Verificar:**
```bash
gh secret list --repo Patricia7sp/AI_film
```

---

## 📋 Método 3: Via Script Python (Automático)

### **Pré-requisitos:**
```bash
# Instalar dependências
pip install PyNaCl requests

# Criar Personal Access Token no GitHub
# https://github.com/settings/tokens
# Permissões necessárias: repo (full control)
```

### **Configurar token:**
```bash
export GITHUB_TOKEN="seu_token_aqui"
```

### **Executar script:**
```bash
python .github/scripts/add_github_secret.py
```

---

## 🔍 Verificar se o Secret foi Adicionado

### **Via Interface Web:**
1. Vá para: https://github.com/Patricia7sp/AI_film/settings/secrets/actions
2. Você deve ver **GEMINI_API_KEY** na lista

### **Via GitHub CLI:**
```bash
gh secret list --repo Patricia7sp/AI_film
```

**Saída esperada:**
```
GEMINI_API_KEY         Updated 2025-10-31
OPENAI_API_KEY         Updated YYYY-MM-DD
ELEVENLABS_API_KEY     Updated YYYY-MM-DD
...
```

---

## 🧪 Testar o Secret no Workflow

### **Disparar workflow manualmente:**

1. **Via Interface Web:**
   - Vá para: https://github.com/Patricia7sp/AI_film/actions
   - Selecione o workflow **Full Auto Colab Pipeline**
   - Clique em **Run workflow**
   - Selecione a branch **main**
   - Clique em **Run workflow**

2. **Via GitHub CLI:**
   ```bash
   gh workflow run "full-auto-colab-pipeline.yml" \
     --repo Patricia7sp/AI_film \
     --ref main
   ```

3. **Via API (Google Colab):**
   ```python
   import requests
   from google.colab import userdata
   
   response = requests.post(
       "https://api.github.com/repos/Patricia7sp/AI_film/dispatches",
       headers={"Authorization": f"token {userdata.get('GITHUB_TOKEN')}"},
       json={
           "event_type": "colab-ready",
           "client_payload": {
               "comfyui_url": "https://sua-url.trycloudflare.com"
           }
       }
   )
   
   print("✅ Workflow disparado!")
   print("👀 https://github.com/Patricia7sp/AI_film/actions")
   ```

---

## 📊 Secrets Necessários para o Projeto

| Secret Name | Descrição | Status |
|-------------|-----------|--------|
| **GEMINI_API_KEY** | Google Gemini API (LLM Principal) | ⚠️ **ADICIONAR** |
| OPENAI_API_KEY | OpenAI API (Fallback) | ✅ Já existe? |
| ELEVENLABS_API_KEY | ElevenLabs (Áudio) | ✅ Já existe? |
| STABILITY_API_KEY | Stability AI (Imagens) | ✅ Já existe? |
| REPLICATE_API_TOKEN | Replicate (Modelos) | ✅ Já existe? |
| GITHUB_TOKEN | GitHub Actions (Auto) | ✅ Automático |
| COLAB_NOTEBOOK_ID | Google Colab ID | ✅ Já existe? |
| COMFYUI_URL_GIST_ID | Gist para ComfyUI URL | ✅ Já existe? |

---

## ⚠️ Segurança

### **Boas Práticas:**

1. ✅ **Nunca commite secrets no código**
   - Use sempre GitHub Secrets
   - Adicione `.env` no `.gitignore`

2. ✅ **Rotacione secrets periodicamente**
   - Troque as API keys a cada 3-6 meses
   - Revogue keys antigas

3. ✅ **Use secrets específicos por ambiente**
   - Desenvolvimento: keys de teste
   - Produção: keys de produção

4. ✅ **Limite permissões**
   - Use tokens com menor privilégio possível
   - Revogue tokens não utilizados

---

## 🔧 Troubleshooting

### **Erro: "Secret not found"**
```bash
# Verifique se o secret existe
gh secret list --repo Patricia7sp/AI_film | grep GEMINI
```

### **Erro: "Unauthorized"**
```bash
# Verifique se o token tem permissões corretas
gh auth status
```

### **Erro: "Invalid secret value"**
```bash
# Verifique se a API key está correta
# Teste manualmente:
curl -H "x-goog-api-key: AIzaSyD6L3PQI5MSmiQvosOrhcQllU4_O3UplP4" \
  "https://generativelanguage.googleapis.com/v1/models"
```

---

## 📝 Checklist Final

- [ ] GEMINI_API_KEY adicionado no GitHub Secrets
- [ ] Secret verificado na interface web
- [ ] Workflow testado manualmente
- [ ] Pipeline executou com sucesso
- [ ] Logs mostram "🤖 LLM: Gemini 2.0 Flash"
- [ ] Custos reduzidos (monitorar)

---

## 🎯 Próximos Passos Após Adicionar o Secret

1. ✅ **Testar localmente:**
   ```bash
   python orchestration/llm_config.py
   ```

2. ✅ **Testar no CI/CD:**
   - Disparar workflow via Colab
   - Verificar logs do GitHub Actions
   - Confirmar que Gemini está sendo usado

3. ✅ **Monitorar custos:**
   - Google Cloud Console
   - Verificar uso da API
   - Comparar com custos anteriores

4. ✅ **Validar qualidade:**
   - Verificar prompts gerados
   - Comparar com prompts anteriores (OpenAI)
   - Ajustar temperatura se necessário

---

## 📚 Links Úteis

- [GitHub Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [GitHub CLI Documentation](https://cli.github.com/manual/)
- [Gemini API Keys](https://makersuite.google.com/app/apikey)
- [Google Cloud Console](https://console.cloud.google.com/)

---

**Data:** 31 de Outubro de 2025  
**Status:** ⚠️ Aguardando adição do GEMINI_API_KEY
