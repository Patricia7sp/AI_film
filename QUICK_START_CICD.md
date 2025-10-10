# 🚀 Quick Start - CI/CD Automatizado

## ⚡ Setup em 5 Minutos

### 1. **Configure Secrets** (2 min)

```bash
# GitHub CLI
gh secret set COMFYUI_FALLBACK_URL -b "https://seu-tunnel.trycloudflare.com"
gh secret set GCP_PROJECT_ID -b "seu-projeto-gcp"
```

Ou via interface: `Settings > Secrets > New repository secret`

### 2. **Ative GitHub Actions** (30 seg)

1. Vá em `Actions` no seu repositório
2. Clique em `Enable workflows`
3. Pronto! ✅

### 3. **Faça seu Primeiro Push** (1 min)

```bash
git checkout -b feature/test-cicd
echo "# Test" >> README.md
git add .
git commit -m "feat: test CI/CD"
git push origin feature/test-cicd
```

### 4. **Veja a Mágica Acontecer** (1 min)

1. Vá em `Actions` no GitHub
2. Veja o workflow executando
3. Aguarde os testes passarem ✅

---

## 🎯 Fluxo Diário de Trabalho

### **Desenvolver Feature**

```bash
# 1. Criar branch
git checkout -b feature/minha-feature develop

# 2. Desenvolver
# ... código aqui ...

# 3. Commit e push
git add .
git commit -m "feat: adiciona funcionalidade X"
git push origin feature/minha-feature

# 4. GitHub Actions executa automaticamente:
#    ✅ Linting
#    ✅ Testes
#    ✅ Validação

# 5. Criar PR
gh pr create --base develop --title "feat: minha feature"
```

### **Atualizar URL do ComfyUI**

```bash
# Método 1: Via GitHub CLI
gh secret set COMFYUI_FALLBACK_URL -b "https://nova-url.trycloudflare.com"

# Método 2: Via script local
python open3d_implementation/scripts/update_comfyui_url.py "https://nova-url.trycloudflare.com"
gh secret set COMFYUI_FALLBACK_URL -b "$(cat open3d_implementation/config/comfyui_config.json | jq -r .base_url)"
```

---

## 🧪 Testes Locais (Antes do Push)

```bash
# Linting rápido
black --check open3d_implementation/
flake8 open3d_implementation/ --max-line-length=120

# Testes unitários
cd open3d_implementation
pytest tests/ -v --maxfail=3

# Teste específico
pytest tests/test_dagster_integration_final.py -v
```

---

## 🏗️ Deploy para Produção

```bash
# 1. Criar release branch
git checkout -b release/v1.0.0 develop

# 2. Atualizar versão
echo "1.0.0" > VERSION

# 3. Commit e push
git add .
git commit -m "chore: release v1.0.0"
git push origin release/v1.0.0

# 4. Merge para main
git checkout main
git merge release/v1.0.0
git tag v1.0.0
git push origin main --tags

# 5. Deploy automático via GitHub Actions! 🚀
```

---

## 🐛 Troubleshooting Rápido

### **Testes Falhando?**

```bash
# Ver logs
gh run view --log

# Reexecutar
gh run rerun
```

### **ComfyUI Não Conecta?**

```bash
# Testar URL
curl https://seu-tunnel.trycloudflare.com

# Atualizar
gh secret set COMFYUI_FALLBACK_URL -b "nova-url"
```

### **Build Docker Falha?**

```bash
# Testar localmente
docker build -t test -f open3d_implementation/Dockerfile open3d_implementation/

# Ver logs
docker logs <container-id>
```

---

## 📊 Monitorar Pipeline

### **Via GitHub**
- Acesse: `https://github.com/seu-usuario/seu-repo/actions`
- Veja status em tempo real
- Logs detalhados de cada step

### **Via CLI**
```bash
# Listar workflows
gh workflow list

# Ver runs recentes
gh run list

# Ver detalhes
gh run view <run-id>
```

---

## 💡 Dicas Pro

1. **Cache de Dependências**: Já configurado! Builds 50% mais rápidos
2. **Testes Paralelos**: Usa `pytest-xdist` automaticamente
3. **Auto-merge**: Configure label `auto-merge` em PRs aprovados
4. **Notificações**: Configure Slack webhook para alertas
5. **Branch Protection**: Ative em `Settings > Branches`

---

## ✅ Checklist Diário

- [ ] Pull latest changes: `git pull origin develop`
- [ ] Criar feature branch: `git checkout -b feature/...`
- [ ] Desenvolver e testar localmente
- [ ] Commit com mensagem clara: `git commit -m "feat: ..."`
- [ ] Push e aguardar CI: `git push origin feature/...`
- [ ] Criar PR quando testes passarem
- [ ] Merge após aprovação

---

## 🎓 Comandos Úteis

```bash
# GitHub CLI
gh auth login                    # Autenticar
gh repo view                     # Ver repositório
gh pr list                       # Listar PRs
gh pr create                     # Criar PR
gh pr merge                      # Merge PR
gh workflow list                 # Listar workflows
gh run list                      # Listar execuções
gh run view                      # Ver detalhes
gh secret list                   # Listar secrets
gh secret set KEY -b "value"     # Criar secret

# Git Flow
git flow init                    # Inicializar GitFlow
git flow feature start nome      # Criar feature
git flow feature finish nome     # Finalizar feature
git flow release start v1.0.0    # Criar release
git flow release finish v1.0.0   # Finalizar release

# Docker
docker build -t app .            # Build
docker run -p 3000:3000 app      # Run
docker logs -f <container>       # Logs
docker exec -it <container> bash # Shell

# Terraform
terraform init                   # Inicializar
terraform plan                   # Ver mudanças
terraform apply                  # Aplicar
terraform destroy                # Destruir
```

---

## 🎉 Pronto!

Agora você tem um **pipeline CI/CD totalmente automatizado**!

**Próximo passo**: Faça um push e veja os testes rodarem automaticamente! 🚀

**Dúvidas?** Consulte o [CICD_SETUP.md](./CICD_SETUP.md) para detalhes completos.
