# 🔐 Atualizar Secrets do GitHub

## ✅ Secrets Criados

Todos os secrets foram criados com valores placeholder. Você precisa atualizar com os valores reais.

```bash
# Ver todos os secrets
gh secret list
```

---

## 📋 Secrets que Precisam ser Atualizados

### **1. COMFYUI_FALLBACK_URL** ⚠️

**Status:** Criado com placeholder
**Ação:** Atualizar com URL real do Colab

```bash
# Depois de rodar o ComfyUI no Colab, copie a URL e execute:
gh secret set COMFYUI_FALLBACK_URL --body "https://sua-url-real.trycloudflare.com"
```

**Como obter:**
1. Abra seu notebook do Colab: https://colab.research.google.com/drive/1bfDjw5JGeqExdsUWYM41txvqlCGzOF99
2. Execute todas as células
3. Copie a URL do Cloudflare que aparece no log
4. Execute o comando acima

---

### **2. KUBE_CONFIG** ⚠️

**Status:** Criado com placeholder
**Ação:** Atualizar após iniciar o minikube

```bash
# 1. Iniciar minikube
minikube start

# 2. Verificar se está rodando
minikube status

# 3. Atualizar secret com configuração real
cat ~/.kube/config | base64 | gh secret set KUBE_CONFIG
```

---

### **3. OPENAI_API_KEY** ⚠️

**Status:** Criado com placeholder
**Ação:** Atualizar com sua chave real da OpenAI

```bash
# Obtenha sua chave em: https://platform.openai.com/api-keys
gh secret set OPENAI_API_KEY --body "sk-proj-sua-chave-real-aqui"
```

---

### **4. ANTHROPIC_API_KEY** ⚠️

**Status:** Criado com placeholder
**Ação:** Atualizar com sua chave real da Anthropic

```bash
# Obtenha sua chave em: https://console.anthropic.com/settings/keys
gh secret set ANTHROPIC_API_KEY --body "sk-ant-sua-chave-real-aqui"
```

---

### **5. POSTGRES_PASSWORD** ✅

**Status:** Criado com senha segura
**Valor:** `aifilm_secure_password_2024`
**Ação:** Opcional - pode manter ou trocar

```bash
# Se quiser trocar:
gh secret set POSTGRES_PASSWORD --body "sua-senha-super-segura"
```

---

### **6. REDIS_PASSWORD** ✅

**Status:** Criado com senha segura
**Valor:** `redis_secure_password_2024`
**Ação:** Opcional - pode manter ou trocar

```bash
# Se quiser trocar:
gh secret set REDIS_PASSWORD --body "sua-senha-super-segura"
```

---

### **7. DOCKER_USERNAME** ✅

**Status:** Criado com seu username
**Valor:** `patricia7sp`
**Ação:** Verificar se está correto

```bash
# Se precisar trocar:
gh secret set DOCKER_USERNAME --body "seu-username-dockerhub"
```

---

## 🔑 Secrets Opcionais (Para Funcionalidades Avançadas)

### **DOCKER_PASSWORD**
Para push automático de imagens Docker

```bash
gh secret set DOCKER_PASSWORD --body "sua-senha-dockerhub"
```

### **GOOGLE_COLAB_CREDENTIALS**
Para automação completa do Colab (OAuth2)

```bash
# Baixe as credenciais do Google Cloud Console
gh secret set GOOGLE_COLAB_CREDENTIALS --body "$(cat credentials.json)"
```

### **COMFYUI_WEBHOOK_URL**
Para captura automática da URL do ComfyUI

```bash
gh secret set COMFYUI_WEBHOOK_URL --body "https://seu-webhook.com/comfyui-url"
```

### **SLACK_WEBHOOK**
Para notificações no Slack

```bash
gh secret set SLACK_WEBHOOK --body "https://hooks.slack.com/services/..."
```

---

## 🚀 Ordem Recomendada de Atualização

### **Fase 1: Setup Básico (Agora)**

```bash
# 1. Iniciar Kubernetes
minikube start

# 2. Atualizar KUBE_CONFIG
cat ~/.kube/config | base64 | gh secret set KUBE_CONFIG

# 3. Verificar
gh secret list
```

### **Fase 2: ComfyUI (Quando for testar)**

```bash
# 1. Rodar ComfyUI no Colab
# 2. Copiar URL do Cloudflare
# 3. Atualizar secret
gh secret set COMFYUI_FALLBACK_URL --body "https://url-real.trycloudflare.com"
```

### **Fase 3: API Keys (Quando for usar LLMs)**

```bash
# OpenAI
gh secret set OPENAI_API_KEY --body "sk-proj-..."

# Anthropic
gh secret set ANTHROPIC_API_KEY --body "sk-ant-..."
```

---

## ✅ Checklist de Secrets

- [x] COMFYUI_FALLBACK_URL (placeholder - atualizar depois)
- [x] KUBE_CONFIG (placeholder - atualizar após minikube start)
- [ ] OPENAI_API_KEY (atualizar com chave real)
- [ ] ANTHROPIC_API_KEY (atualizar com chave real)
- [x] POSTGRES_PASSWORD (OK - senha gerada)
- [x] REDIS_PASSWORD (OK - senha gerada)
- [x] DOCKER_USERNAME (OK - patricia7sp)
- [ ] DOCKER_PASSWORD (opcional - para CI/CD)

---

## 🔍 Verificar Secrets

```bash
# Listar todos
gh secret list

# Ver quando foi atualizado
gh secret list | grep COMFYUI

# Deletar um secret (se necessário)
gh secret delete NOME_DO_SECRET
```

---

## 🎯 Próximos Passos

1. **Agora:** Iniciar minikube e atualizar KUBE_CONFIG
2. **Depois:** Rodar Colab e atualizar COMFYUI_FALLBACK_URL
3. **Quando precisar:** Adicionar API keys reais

```bash
# Comando rápido para iniciar tudo:
minikube start && \
cat ~/.kube/config | base64 | gh secret set KUBE_CONFIG && \
echo "✅ KUBE_CONFIG atualizado!" && \
gh secret list
```

---

## 📚 Recursos

- **GitHub Secrets:** https://github.com/Patricia7sp/AI_film/settings/secrets/actions
- **OpenAI API Keys:** https://platform.openai.com/api-keys
- **Anthropic API Keys:** https://console.anthropic.com/settings/keys
- **Docker Hub:** https://hub.docker.com/settings/security

**Tudo pronto para começar!** 🚀
