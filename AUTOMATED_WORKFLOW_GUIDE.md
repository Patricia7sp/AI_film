# 🤖 Fluxo Automatizado Inteligente - Colab + GitHub Actions

**Sistema 100% Automatizado com Trigger Inteligente**

---

## 🎯 Como Funciona (Seu Sistema Atual)

```
┌─────────────────────────────────────────────────────────────┐
│                    FLUXO AUTOMATIZADO                        │
└─────────────────────────────────────────────────────────────┘

1. 📝 Você faz mudanças no código localmente
2. 🚀 Executa: python3 scripts/auto_deploy.py
3. 📤 Script commita e faz push para GitHub
4. 🤖 GitHub Actions detecta push automaticamente
5. 🎬 Workflow dispara Colab (via Playwright/webhook)
6. 💻 Colab executa notebook automaticamente:
   ├── Instala ComfyUI
   ├── Inicia Cloudflare Tunnel
   ├── Captura URL
   └── Reporta URL para GitHub Gist
7. 🔄 GitHub Actions detecta URL no Gist
8. ✅ Pipeline continua automaticamente
9. 🧪 Testes de integração executam
10. 🎉 Deploy completo!
```

---

## 📋 Pré-requisitos

### **Já Configurado:**
- ✅ Notebook Colab (`colab_automated_notebook.ipynb`)
- ✅ Workflows GitHub Actions (8 workflows)
- ✅ Sistema de trigger automático

### **Precisa Configurar:**
- [ ] GitHub Secrets (se ainda não tem)
- [ ] Gist ID para URL do ComfyUI
- [ ] Webhook/Playwright para disparar Colab

---

## 🚀 Uso Diário

### **Fluxo Completo (Recomendado):**

```bash
# 1. Fazer mudanças no código
# ... editar arquivos ...

# 2. Executar diagnóstico (valida mudanças)
python3 scripts/diagnose_system.py

# 3. Deploy automático (commita + push + dispara CI/CD)
python3 scripts/auto_deploy.py -m "feat: adiciona nova funcionalidade"

# 4. Acompanhar pipeline
# GitHub Actions → https://github.com/SEU_USUARIO/LANGGRAPH_MCP/actions
```

### **Apenas Verificar Mudanças:**

```bash
# Dry run (não commita)
python3 scripts/auto_deploy.py --dry-run
```

### **Deploy Rápido:**

```bash
# Usa mensagem padrão
python3 scripts/auto_deploy.py
```

---

## 🔧 Configuração Inicial (Se Necessário)

### **1. GitHub Secrets**

Configure em: `Settings → Secrets and variables → Actions`

```bash
# Necessários para o workflow
GITHUB_TOKEN              # Token de acesso (auto-gerado)
COLAB_NOTEBOOK_ID         # ID do notebook no Colab
COMFYUI_URL_GIST_ID      # ID do Gist para URL
COLAB_TRIGGER_WEBHOOK     # Webhook para disparar Colab (opcional)
COMFYUI_FALLBACK_URL     # URL fallback (opcional)
```

### **2. Criar Gist para URL**

```bash
# Criar Gist via gh CLI
gh gist create --public -d "ComfyUI URL" -f comfyui_url.json - <<< '{"url": "", "status": "pending"}'

# Copiar o ID do Gist e adicionar aos secrets
gh secret set COMFYUI_URL_GIST_ID -b "SEU_GIST_ID"
```

### **3. Configurar Notebook Colab**

O notebook já está pronto em: `colab_automated_notebook.ipynb`

**Importante:** Certifique-se que o notebook tem acesso aos secrets via variáveis de ambiente.

---

## 📊 Workflows Disponíveis

### **1. full-auto-colab-pipeline.yml** (Principal)
- Dispara automaticamente no push
- Orquestra Colab
- Captura URL do ComfyUI
- Executa pipeline completo

### **2. ci-cd-pipeline.yml**
- Testes de qualidade
- Linting
- Coverage

### **3. deploy-with-colab.yml**
- Deploy específico com Colab
- Usado para releases

---

## 🔄 Fluxo Detalhado

### **Quando você faz push:**

```yaml
# GitHub Actions detecta push
on:
  push:
    branches: [main, develop]

# Workflow executa:
jobs:
  orchestrate-colab:
    - Verifica se Colab precisa ser iniciado
    - Dispara Colab via Playwright/webhook
    - Aguarda URL no Gist (polling)
    - Continua pipeline com URL capturada
  
  run-tests:
    - Executa testes com ComfyUI ativo
    - Valida integração
  
  deploy:
    - Deploy se tudo passar
```

### **No Colab:**

```python
# Notebook executa automaticamente:
1. Instala ComfyUI
2. Inicia servidor (porta 8188)
3. Inicia Cloudflare Tunnel
4. Captura URL do log
5. Reporta para GitHub Gist
6. Mantém ativo (keep-alive)
```

---

## 🐛 Troubleshooting

### **Workflow não dispara**

```bash
# Verificar workflows
gh workflow list

# Ver runs recentes
gh run list

# Ver logs de um run
gh run view RUN_ID --log
```

### **Colab não inicia**

1. Verificar secrets configurados
2. Verificar webhook/Playwright
3. Executar notebook manualmente uma vez

### **URL não é capturada**

1. Verificar logs do Colab
2. Verificar Gist ID correto
3. Verificar permissões do GITHUB_TOKEN

---

## 💡 Melhorias Sugeridas

### **1. Notificações**

Adicionar notificações quando pipeline completa:

```yaml
- name: Notify on success
  if: success()
  uses: actions/github-script@v7
  with:
    script: |
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        body: '✅ Pipeline completado com sucesso!'
      })
```

### **2. Cache de Dependências**

```yaml
- name: Cache pip
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

### **3. Retry Automático**

Se Colab falhar, tentar novamente:

```yaml
- name: Start Colab
  uses: nick-invision/retry@v2
  with:
    timeout_minutes: 10
    max_attempts: 3
    command: python scripts/trigger_colab.py
```

---

## 📚 Arquivos Importantes

```
LANGGRAPH_MCP/
├── colab_automated_notebook.ipynb          # Notebook Colab
├── .github/workflows/
│   ├── full-auto-colab-pipeline.yml       # Workflow principal
│   ├── ci-cd-pipeline.yml                 # CI/CD
│   └── deploy-with-colab.yml              # Deploy
├── scripts/
│   ├── auto_deploy.py                     # Deploy automático ✨ NOVO
│   ├── diagnose_system.py                 # Diagnóstico
│   └── monitor_cloudflare.py              # Monitor
└── open3d_implementation/
    └── .env                                # Configurações
```

---

## ✅ Checklist de Validação

- [ ] Secrets configurados no GitHub
- [ ] Gist criado para URL
- [ ] Notebook Colab testado manualmente
- [ ] Workflow dispara no push
- [ ] URL é capturada automaticamente
- [ ] Pipeline completa end-to-end
- [ ] Testes passam
- [ ] Deploy funciona

---

## 🚀 Próximos Passos

### **Agora:**

1. Executar diagnóstico:
   ```bash
   python3 scripts/diagnose_system.py
   ```

2. Se score >= 88%, fazer deploy:
   ```bash
   python3 scripts/auto_deploy.py -m "chore: update Gemini API configuration"
   ```

3. Acompanhar workflow:
   ```bash
   gh run watch
   ```

### **Depois:**

- Monitorar Cloudflare: `python3 scripts/monitor_cloudflare.py`
- Verificar logs do Colab
- Validar geração de imagens
- Testar pipeline completo

---

**Tempo de setup:** Já está pronto! ✅  
**Tempo de deploy:** ~5 minutos (automático)  
**Custo:** Colab Pro (você já paga)

---

## 🆘 Suporte

Se algo falhar:

1. Verificar logs do workflow
2. Verificar logs do Colab
3. Executar diagnóstico
4. Verificar secrets configurados

---

**Sistema 100% automatizado e inteligente!** 🤖✨
