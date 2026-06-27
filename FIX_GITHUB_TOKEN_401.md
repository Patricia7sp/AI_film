# 🔧 Corrigir Erro 401 - GitHub Token

## ❌ Problema

```
❌ Erro: 401
```

Isso significa que o `GITHUB_TOKEN` está:
- ❌ Inválido
- ❌ Expirado
- ❌ Sem permissões necessárias

---

## ✅ Solução Rápida

### **PASSO 1: Criar Novo Token**

```bash
# Via gh CLI (recomendado):
gh auth refresh -s workflow,gist

# Copiar token:
gh auth token
```

**Ou manualmente:**

1. Acesse: https://github.com/settings/tokens
2. Clique em **"Generate new token"** → **"Classic"**
3. Configure:
   - **Note:** `Colab AI Film Pipeline`
   - **Expiration:** `No expiration` (ou 90 days)
   - **Scopes:**
     - ✅ `workflow` (Workflow)
     - ✅ `gist` (Create gists)
     - ✅ `repo` (Full control of private repositories)
4. Clique **"Generate token"**
5. **COPIE O TOKEN** (só aparece uma vez!)

---

### **PASSO 2: Atualizar no Colab**

No Google Colab:

1. Clique no ícone **🔑** (Secrets) na barra lateral
2. Encontre `GITHUB_TOKEN`
3. Clique em **"Edit"** (lápis)
4. Cole o **novo token**
5. ✅ Salvar

---

### **PASSO 3: Re-executar Célula**

No notebook, execute novamente a célula do **Auto-Reporter** (última célula).

Você deve ver:

```
✅ GitHub Actions disparado com sucesso!
👀 Acompanhe: https://github.com/Patricia7sp/AI_film/actions
```

---

## 🔍 Verificar Token

Teste se o token funciona:

```bash
# Testar token
curl -H "Authorization: token SEU_TOKEN_AQUI" \
  https://api.github.com/user

# Deve retornar seus dados do GitHub
# Se retornar 401, o token está inválido
```

---

## 🐛 Troubleshooting

### **Erro persiste após criar novo token?**

Verifique se o token tem as permissões corretas:

```bash
# Listar permissões do token
gh auth status

# Deve mostrar:
# ✓ Logged in to github.com as USERNAME
# ✓ Token: ghp_****
# ✓ Token scopes: gist, repo, workflow
```

### **Token correto mas erro 401?**

O repositório pode ser privado. Adicione permissão `repo`:

1. Vá em: https://github.com/settings/tokens
2. Edite o token
3. Marque: ✅ `repo` (Full control)
4. Salve

---

## ✅ Checklist

- [ ] Criar novo token com permissões: `workflow`, `gist`, `repo`
- [ ] Copiar token
- [ ] Atualizar no Colab (🔑 Secrets)
- [ ] Re-executar célula do Auto-Reporter
- [ ] Verificar se disparou: https://github.com/Patricia7sp/AI_film/actions

---

## 📊 Permissões Necessárias

```
workflow  → Disparar GitHub Actions
gist      → Atualizar Gist com URL
repo      → Acessar repositório (se privado)
```

---

**Tempo:** 2 minutos  
**Depois disso, vai funcionar!** ✅
