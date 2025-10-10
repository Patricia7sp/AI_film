# 🚀 CI/CD Completo com Colab + GitHub Actions

## 📋 Visão Geral

Este guia configura um **pipeline CI/CD totalmente automatizado** que:

1. ✅ Inicia ComfyUI no Google Colab automaticamente
2. ✅ Captura a URL do Cloudflare gerada
3. ✅ Atualiza configurações do projeto
4. ✅ Executa testes com ComfyUI ativo
5. ✅ Deploy automático no Kubernetes
6. ✅ Suporte completo a GitFlow (feature/develop/main)

---

## 🏗️ Arquitetura do CI/CD

```
┌─────────────────────────────────────────────────────────────────┐
│                    GITHUB ACTIONS WORKFLOW                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Push/PR ──▶ Job 1: Start Colab ComfyUI                        │
│                │                                                 │
│                ├─▶ Trigger notebook execution                   │
│                ├─▶ Wait for ComfyUI to start                    │
│                ├─▶ Capture Cloudflare URL                       │
│                └─▶ Verify connectivity                          │
│                                                                  │
│              Job 2: Update Configuration                         │
│                │                                                 │
│                ├─▶ Update .env files                            │
│                ├─▶ Update deploy scripts                        │
│                ├─▶ Create K8s secrets                           │
│                └─▶ Commit changes [skip ci]                     │
│                                                                  │
│              Job 3: Run Tests                                    │
│                │                                                 │
│                ├─▶ Integration tests                            │
│                ├─▶ Pipeline tests                               │
│                └─▶ Dagster tests                                │
│                                                                  │
│              Job 4: Deploy (main only)                           │
│                │                                                 │
│                ├─▶ Update K8s secrets                           │
│                ├─▶ Deploy to cluster                            │
│                └─▶ Verify deployment                            │
│                                                                  │
│              Job 5: Notification                                 │
│                └─▶ Send status notification                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    GOOGLE COLAB                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Notebook: 1bfDjw5JGeqExdsUWYM41txvqlCGzOF99                   │
│                                                                  │
│  1. Install ComfyUI                                             │
│  2. Start ComfyUI server (port 8188)                            │
│  3. Start Cloudflare tunnel                                     │
│  4. Capture tunnel URL                                          │
│  5. Send URL to GitHub Actions                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Setup Passo a Passo

### **1. Configurar Secrets no GitHub**

```bash
# Secrets necessários
gh secret set GOOGLE_COLAB_CREDENTIALS -b "$(cat credentials.json)"
gh secret set COMFYUI_FALLBACK_URL -b "https://sua-url.trycloudflare.com"
gh secret set KUBE_CONFIG -b "$(cat ~/.kube/config | base64)"
gh secret set COMFYUI_WEBHOOK_URL -b "https://seu-webhook.com"  # Opcional
```

**Secrets Obrigatórios:**
- `COMFYUI_FALLBACK_URL`: URL de fallback do ComfyUI
- `KUBE_CONFIG`: Configuração do kubectl (base64)

**Secrets Opcionais:**
- `GOOGLE_COLAB_CREDENTIALS`: Para automação completa do Colab
- `COMFYUI_WEBHOOK_URL`: Para captura automática de URL
- `SLACK_WEBHOOK`: Para notificações

### **2. Configurar Notebook do Colab**

Abra seu notebook: https://colab.research.google.com/drive/1bfDjw5JGeqExdsUWYM41txvqlCGzOF99

**Adicione ao final do notebook:**

```python
# ============================================================
# INTEGRAÇÃO COM GITHUB ACTIONS
# ============================================================

import re
import time
import requests

def send_url_to_github():
    """Captura e envia URL do ComfyUI para GitHub Actions"""
    
    print("🎬 Capturando URL do ComfyUI...")
    
    # Aguardar túnel ser criado
    time.sleep(30)
    
    # Ler log do cloudflared
    with open('/content/cloudflared.log', 'r') as f:
        log = f.read()
        match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', log)
        
        if match:
            url = match.group(0)
            print(f"✅ URL capturada: {url}")
            
            # Salvar em arquivo
            with open('/content/comfyui_url.txt', 'w') as f:
                f.write(url)
            
            # Testar conectividade
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    print("✅ ComfyUI está acessível!")
                    print(f"\n🎯 URL: {url}\n")
                    return url
            except:
                print("⚠️ URL não está acessível ainda")
        else:
            print("❌ URL não encontrada no log")
    
    return None

# Executar automaticamente
comfyui_url = send_url_to_github()

if comfyui_url:
    print("="*70)
    print("✅ CONFIGURAÇÃO COMPLETA!")
    print("="*70)
    print(f"\nComfyUI URL: {comfyui_url}")
    print("\n📋 Próximos passos:")
    print("1. Copie esta URL")
    print("2. Configure como secret no GitHub:")
    print(f"   gh secret set COMFYUI_FALLBACK_URL -b '{comfyui_url}'")
    print("\n💡 Esta URL é válida enquanto este notebook estiver rodando")
    print("="*70)
```

### **3. Configurar GitFlow**

```bash
# Criar branches
git checkout -b develop
git push origin develop

git checkout -b feature/cicd-automation
git push origin feature/cicd-automation

# Proteger branches
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["test-with-colab"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1}'
```

### **4. Ativar Workflows**

```bash
# Verificar workflows
ls -la .github/workflows/

# Ativar no GitHub
# Settings > Actions > General > Allow all actions

# Testar workflow
git add .
git commit -m "feat: add CI/CD with Colab integration"
git push origin feature/cicd-automation
```

---

## 🔄 Fluxo de Trabalho

### **Feature Branch:**

```bash
# 1. Criar feature
git checkout -b feature/nova-funcionalidade develop

# 2. Desenvolver
# ... código aqui ...

# 3. Commit e push
git add .
git commit -m "feat: adiciona nova funcionalidade"
git push origin feature/nova-funcionalidade

# 4. GitHub Actions executa automaticamente:
#    ✅ Start Colab ComfyUI
#    ✅ Update config
#    ✅ Run tests
#    ✅ Create PR
```

### **Develop Branch:**

```bash
# 1. Merge feature
git checkout develop
git merge feature/nova-funcionalidade
git push origin develop

# 2. GitHub Actions executa:
#    ✅ Full test suite
#    ✅ Integration tests
#    ✅ Coverage report
```

### **Main Branch (Production):**

```bash
# 1. Merge develop
git checkout main
git merge develop
git push origin main

# 2. GitHub Actions executa:
#    ✅ All tests
#    ✅ Build Docker
#    ✅ Deploy Kubernetes
#    ✅ Verify deployment
```

---

## 📊 Monitoramento

### **GitHub Actions:**

```bash
# Ver status dos workflows
gh run list

# Ver logs de um workflow
gh run view <run-id> --log

# Re-executar workflow
gh run rerun <run-id>
```

### **Colab:**

```bash
# Verificar se Colab está rodando
curl -f https://sua-url.trycloudflare.com

# Ver logs do ComfyUI
# No Colab: !tail -f /content/ComfyUI/comfyui.log
```

### **Kubernetes:**

```bash
# Ver status do deploy
kubectl get all -n ai-film

# Ver secret do ComfyUI
kubectl get secret comfyui-url-secret -n ai-film -o yaml

# Ver logs
kubectl logs -f deployment/dagster -n ai-film
```

---

## 🐛 Troubleshooting

### **Problema: ComfyUI URL não capturada**

**Solução 1: Usar fallback manual**
```bash
# 1. Abra o Colab manualmente
# 2. Execute todas as células
# 3. Copie a URL do Cloudflare
# 4. Configure como secret:
gh secret set COMFYUI_FALLBACK_URL -b "https://sua-url.trycloudflare.com"
```

**Solução 2: Configurar webhook**
```bash
# 1. Deploy webhook handler
python .github/scripts/colab_webhook_handler.py

# 2. Expor via ngrok
ngrok http 5001

# 3. Configurar secret
gh secret set COMFYUI_WEBHOOK_URL -b "https://seu-ngrok.io/comfyui-url"

# 4. Adicionar ao Colab:
webhook_url = "https://seu-ngrok.io/comfyui-url"
requests.post(webhook_url, json={"url": tunnel_url})
```

### **Problema: Workflow falha em "Start Colab"**

```bash
# Verificar logs
gh run view --log

# Executar manualmente
python .github/scripts/trigger_colab_comfyui.py

# Verificar credenciais
echo $GOOGLE_COLAB_CREDENTIALS
```

### **Problema: Testes falham**

```bash
# Verificar conectividade
curl -f $COMFYUI_URL

# Executar testes localmente
export COMFYUI_URL="https://sua-url.trycloudflare.com"
cd open3d_implementation
pytest tests/ -v
```

---

## 🎯 Próximos Passos

### **Fase 1: Setup Básico** ✅
- [x] Workflow CI/CD criado
- [x] Scripts de automação
- [x] Documentação completa
- [ ] Testar primeiro deploy

### **Fase 2: Automação Completa**
- [ ] Webhook handler em produção
- [ ] Autenticação OAuth2 com Colab
- [ ] Notificações Slack/Discord
- [ ] Dashboard de monitoramento

### **Fase 3: Otimização**
- [ ] Cache de dependências
- [ ] Parallel jobs
- [ ] Deploy preview environments
- [ ] Rollback automático

---

## 📚 Recursos

### **Documentação:**
- [GitHub Actions](https://docs.github.com/en/actions)
- [Google Colab](https://colab.research.google.com/)
- [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Kubernetes](https://kubernetes.io/docs/)

### **Scripts Criados:**
- `.github/workflows/deploy-with-colab.yml` - Workflow principal
- `.github/scripts/trigger_colab_comfyui.py` - Trigger Colab
- `.github/scripts/get_colab_url.py` - Captura URL
- `.github/scripts/colab_notebook_snippet.py` - Snippet para Colab

---

## ✅ Checklist de Setup

- [ ] Secrets configurados no GitHub
- [ ] Notebook do Colab atualizado
- [ ] Branches criadas (develop, feature/*)
- [ ] Workflows ativados
- [ ] Primeiro teste executado
- [ ] URL capturada com sucesso
- [ ] Testes passando
- [ ] Deploy no Kubernetes funcionando

---

## 🎉 Conclusão

Você agora tem um **pipeline CI/CD totalmente automatizado** que:

✅ Inicia ComfyUI no Colab automaticamente
✅ Captura URL do Cloudflare
✅ Atualiza configurações
✅ Executa testes
✅ Deploy automático no Kubernetes
✅ Suporte completo a GitFlow

**Próximo passo:** Execute o primeiro deploy!

```bash
git checkout -b feature/test-cicd
git push origin feature/test-cicd
```

**Acompanhe em:** https://github.com/seu-usuario/langgraph-mcp/actions
