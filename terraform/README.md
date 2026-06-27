# 🏗️ Terraform - GitHub Secrets Management

Gerenciamento automatizado de secrets do GitHub usando Terraform.

---

## 📋 Pré-requisitos

### 1. **Instalar Terraform**

```bash
# macOS
brew install terraform

# Linux
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Verificar instalação
terraform version
```

### 2. **Criar GitHub Personal Access Token**

1. Acesse: https://github.com/settings/tokens
2. Clique em **Generate new token (classic)**
3. Dê um nome: `Terraform GitHub Secrets`
4. Selecione permissões:
   - ✅ **repo** (Full control of private repositories)
5. Clique em **Generate token**
6. **Copie o token** (você não verá novamente!)

---

## 🚀 Como Usar

### **Passo 1: Configurar Variáveis**

```bash
cd terraform

# Copiar arquivo de exemplo
cp terraform.tfvars.example terraform.tfvars

# Editar com seus valores
nano terraform.tfvars
```

**Conteúdo do `terraform.tfvars`:**
```hcl
github_token      = "your-github-token"
github_owner      = "Patricia7sp"
github_repository = "AI_film"

gemini_api_key    = "your-gemini-api-key"
```

### **Passo 2: Inicializar Terraform**

```bash
terraform init
```

**Saída esperada:**
```
Initializing the backend...
Initializing provider plugins...
- Finding integrations/github versions matching "~> 5.0"...
- Installing integrations/github v5.x.x...

Terraform has been successfully initialized!
```

### **Passo 3: Planejar Mudanças**

```bash
terraform plan
```

**Saída esperada:**
```
Terraform will perform the following actions:

  # github_actions_secret.gemini_api_key will be created
  + resource "github_actions_secret" "gemini_api_key" {
      + created_at      = (known after apply)
      + id              = (known after apply)
      + plaintext_value = (sensitive value)
      + repository      = "AI_film"
      + secret_name     = "GEMINI_API_KEY"
      + updated_at      = (known after apply)
    }

Plan: 1 to add, 0 to change, 0 to destroy.
```

### **Passo 4: Aplicar Mudanças**

```bash
terraform apply
```

Digite `yes` quando solicitado.

**Saída esperada:**
```
github_actions_secret.gemini_api_key: Creating...
github_actions_secret.gemini_api_key: Creation complete after 2s

Apply complete! Resources: 1 added, 0 changed, 0 destroyed.

Outputs:

repository_url = "https://github.com/Patricia7sp/AI_film"
secrets_created = [
  "GEMINI_API_KEY",
]
secrets_url = "https://github.com/Patricia7sp/AI_film/settings/secrets/actions"
```

### **Passo 5: Verificar**

```bash
# Ver outputs
terraform output

# Acessar URL dos secrets
open $(terraform output -raw secrets_url)
```

---

## 🔧 Comandos Úteis

### **Ver estado atual:**
```bash
terraform show
```

### **Ver outputs:**
```bash
terraform output
terraform output -json
```

### **Atualizar um secret:**
```bash
# Editar terraform.tfvars
nano terraform.tfvars

# Aplicar mudanças
terraform apply
```

### **Remover todos os secrets:**
```bash
terraform destroy
```

### **Validar configuração:**
```bash
terraform validate
```

### **Formatar código:**
```bash
terraform fmt
```

---

## 📊 Estrutura de Arquivos

```
terraform/
├── github_secrets.tf          # Configuração principal
├── terraform.tfvars.example   # Exemplo de variáveis
├── terraform.tfvars           # Suas variáveis (não commitar!)
├── .terraform/                # Diretório do Terraform (gerado)
├── terraform.tfstate          # Estado do Terraform (não commitar!)
└── README.md                  # Este arquivo
```

---

## ⚠️ Segurança

### **Arquivos Sensíveis (NÃO COMMITAR):**

```gitignore
# .gitignore
terraform/terraform.tfvars
terraform/.terraform/
terraform/terraform.tfstate
terraform/terraform.tfstate.backup
terraform/.terraform.lock.hcl
```

### **Boas Práticas:**

1. ✅ **Nunca commite `terraform.tfvars`**
   - Contém secrets em texto plano
   - Use `.gitignore`

2. ✅ **Use backend remoto (opcional)**
   ```hcl
   terraform {
     backend "s3" {
       bucket = "seu-bucket-terraform"
       key    = "github-secrets/terraform.tfstate"
       region = "us-east-1"
     }
   }
   ```

3. ✅ **Rotacione tokens periodicamente**
   - GitHub tokens: a cada 3-6 meses
   - API keys: conforme necessário

4. ✅ **Use variáveis de ambiente (alternativa)**
   ```bash
   export TF_VAR_github_token="your-github-token"
   export TF_VAR_gemini_api_key="your-gemini-api-key"
   terraform apply
   ```

---

## 🔄 Workflow Completo

### **Setup Inicial:**
```bash
# 1. Instalar Terraform
brew install terraform

# 2. Criar token no GitHub
# https://github.com/settings/tokens

# 3. Configurar variáveis
cd terraform
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars

# 4. Inicializar
terraform init

# 5. Aplicar
terraform plan
terraform apply
```

### **Atualizar Secrets:**
```bash
# 1. Editar valores
nano terraform.tfvars

# 2. Aplicar mudanças
terraform apply
```

### **Verificar:**
```bash
# Ver secrets no GitHub
open https://github.com/Patricia7sp/AI_film/settings/secrets/actions

# Ou via CLI
gh secret list --repo Patricia7sp/AI_film
```

---

## 🧪 Testar Secrets

### **Via GitHub Actions:**

```bash
# Disparar workflow
gh workflow run "full-auto-colab-pipeline.yml" \
  --repo Patricia7sp/AI_film \
  --ref main

# Ver logs
gh run list --repo Patricia7sp/AI_film
gh run view <run-id> --log
```

### **Via API:**

```python
import requests
import os

response = requests.post(
    "https://api.github.com/repos/Patricia7sp/AI_film/dispatches",
    headers={"Authorization": f"token {os.getenv('GITHUB_TOKEN')}"},
    json={
        "event_type": "colab-ready",
        "client_payload": {
            "comfyui_url": "https://sua-url.trycloudflare.com"
        }
    }
)

print("✅ Workflow disparado!")
```

---

## 🔧 Troubleshooting

### **Erro: "Error: GET https://api.github.com/repos/.../actions/secrets/public-key: 404"**

**Causa:** Token sem permissões ou repositório incorreto

**Solução:**
```bash
# Verificar token
echo $TF_VAR_github_token

# Verificar repositório
terraform console
> var.github_repository
```

### **Erro: "Error: Insufficient permissions"**

**Causa:** Token sem permissão `repo`

**Solução:**
1. Vá para https://github.com/settings/tokens
2. Edite o token
3. Marque **repo** (Full control)
4. Salve

### **Erro: "Error: Secret already exists"**

**Causa:** Secret já existe no GitHub

**Solução:**
```bash
# Importar estado existente
terraform import github_actions_secret.gemini_api_key AI_film:GEMINI_API_KEY

# Ou remover e recriar
gh secret remove GEMINI_API_KEY --repo Patricia7sp/AI_film
terraform apply
```

---

## 📚 Recursos

- [Terraform GitHub Provider](https://registry.terraform.io/providers/integrations/github/latest/docs)
- [Terraform Documentation](https://www.terraform.io/docs)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)

---

## 🎯 Vantagens do Terraform

✅ **Infraestrutura como Código**
- Versionável
- Reproduzível
- Auditável

✅ **Automação**
- Um comando para criar todos os secrets
- Fácil de atualizar

✅ **Idempotente**
- Pode executar múltiplas vezes
- Só aplica mudanças necessárias

✅ **State Management**
- Rastreia estado atual
- Detecta drift

---

**Data:** 31 de Outubro de 2025  
**Versão:** 1.0  
**Status:** ✅ Pronto para uso
