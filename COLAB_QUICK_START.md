# 🚀 **Quick Start - Colab + GitHub Actions Automático**

## **⚡ Setup em 3 Minutos**

### **Passo 1: Adicionar ao Notebook Colab**

1. Abra seu notebook no **Google Colab**
2. **Crie uma nova célula** logo após os imports
3. **Copie e cole** o código de `colab_complete_setup.py`
4. **Configure no topo do código:**

```python
# CONFIGURAÇÃO - AJUSTE AQUI!
TIMEOUT_MINUTES = 30  # 30 min = econômico, 60 = balanceado

# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # ou "ghp_seu_token"
GITHUB_REPO = "Patricia7sp/AI_film"

# Gist
GIST_ID = os.getenv("COMFYUI_URL_GIST_ID")  # ou "seu_gist_id"

# ComfyUI (será obtido automaticamente após iniciar)
COMFYUI_URL = os.getenv("COMFYUI_URL")
```

5. **Execute a célula** ▶️

---

### **Passo 2: Configurar Auto-Run**

1. No Colab: **`Tools > Settings`**
2. Marcar: **☑️ "Run all cells on load"**
3. **Salvar** (Ctrl+S)

---

### **Passo 3: Configurar ComfyUI URL**

Após o ComfyUI iniciar, adicione esta célula:

```python
# Após ComfyUI iniciar, defina a URL
comfyui_url = "https://xxx.trycloudflare.com"  # Sua URL aqui

# Atualizar sistema e disparar GitHub Actions
set_comfyui_url(comfyui_url)
```

**Pronto!** 🎉

---

## **🎯 Como Usar no Dia a Dia**

### **Fluxo Completo:**

```
1. Você abre o notebook Colab (1 clique)
   ↓
2. Notebook executa automaticamente
   ↓
3. ComfyUI inicia
   ↓
4. Sistema:
   - Publica URL no Gist
   - Dispara GitHub Actions automaticamente 🚀
   - Monitora inatividade
   ↓
5. Você acompanha pipeline no GitHub Actions 👀
   ↓
6. Após 30min sem uso → Auto-shutdown 💰
```

---

## **📊 O Que o Sistema Faz Automaticamente**

### ✅ **Quando você abre o Colab:**

1. **Monitor de Inatividade** inicia
   - Checa a cada 1 minuto
   - Auto-shutdown após 30-60min sem uso
   - Avisos progressivos (5min, 2min, 1min)

2. **Atualização do Gist**
   - URL do ComfyUI
   - Status (active/idle/offline)
   - Timestamp de última atividade
   - Tempo até shutdown

3. **Trigger do GitHub Actions**
   - Dispara automaticamente quando pronto
   - Payload com URL do ComfyUI
   - Você acompanha em tempo real

4. **Timer Inteligente**
   - Reseta automaticamente com cada requisição
   - Se você está usando, nunca desconecta
   - Economiza quando inativo

---

## **👀 Acompanhando o Pipeline**

### **No GitHub:**
```
https://github.com/Patricia7sp/AI_film/actions
```

### **Status em Tempo Real:**

O sistema atualiza o Gist a cada 5 minutos com:

```json
{
  "comfyui_url": "https://xxx.trycloudflare.com",
  "status": "active",
  "last_activity": "2025-10-13T20:15:00Z",
  "uptime_minutes": 25,
  "inactive_minutes": 5,
  "auto_shutdown_in_minutes": 25,
  "total_requests": 42,
  "github_actions_triggered": true
}
```

---

## **💰 Economia**

| Sem Sistema | Com Sistema |
|-------------|-------------|
| 24h/dia rodando | ~3h/dia rodando |
| 720h/mês | 90h/mês |
| Units esgotam em 7 dias | Units duram mês todo |
| $40-80/mês | $9.99/mês |
| **0% economia** | **🎉 83% economia!** |

---

## **🔧 Funções Úteis**

### **Manter Ativo Manualmente:**
```python
keep_alive()  # Reseta timer de inatividade
```

### **Atualizar URL do ComfyUI:**
```python
set_comfyui_url("https://nova-url.trycloudflare.com")
# Atualiza Gist + Dispara GitHub Actions automaticamente
```

### **Forçar Shutdown:**
```python
force_shutdown()  # Desconecta imediatamente
```

---

## **⚙️ Configurações**

### **Ajustar Timeout:**

```python
# Muito econômico (recomendado)
TIMEOUT_MINUTES = 30

# Balanceado
TIMEOUT_MINUTES = 60

# Flexível (desenvolvimento longo)
TIMEOUT_MINUTES = 90
```

### **Desabilitar Auto-Trigger do GitHub:**

```python
manager.start(auto_trigger_github=False)
```

### **Disparar GitHub Actions Manualmente:**

```python
manager.trigger_github_actions()
```

---

## **🐛 Troubleshooting**

### **"GitHub Actions não foi disparado"**

Verifique:
- ✅ `GITHUB_TOKEN` tem permissão `workflow`
- ✅ `GITHUB_REPO` está correto ("owner/repo")
- ✅ Workflow aceita `repository_dispatch: types: [colab-ready]`

Testar manualmente:
```python
manager.trigger_github_actions()
```

### **"Gist não está atualizando"**

Verifique:
- ✅ `GIST_ID` está correto
- ✅ `GITHUB_TOKEN` tem permissão `gist`

Testar manualmente:
```python
manager.update_gist("active")
```

### **"Sistema desconectou enquanto eu estava usando"**

- Verifique se as requisições estão chegando ao ComfyUI
- Timer só reseta com requisições ativas
- Pode aumentar `TIMEOUT_MINUTES` se necessário

---

## **✅ Checklist**

- [ ] Código adicionado ao notebook Colab
- [ ] `TIMEOUT_MINUTES` configurado
- [ ] `GITHUB_TOKEN` configurado (com scope `workflow`)
- [ ] `GITHUB_REPO` configurado
- [ ] `GIST_ID` configurado
- [ ] "Run all cells on load" ativado
- [ ] Workflow aceita `repository_dispatch`
- [ ] Testado: abrir Colab → Actions dispara automaticamente
- [ ] Testado: auto-shutdown funciona

---

## **🎉 Resultado Final**

Agora você tem:

✅ **95% de automação**
- Você: 1 clique no Colab
- Sistema: TODO o resto

✅ **83-92% de economia**
- Auto-shutdown inteligente
- $30-70/mês economizados

✅ **Visibilidade total**
- Acompanha pipeline no GitHub Actions
- Status em tempo real via Gist

✅ **Flexível**
- Timeout configurável
- Timer reseta com uso
- Funções de controle manual

---

**Pronto para usar! 🚀**

Dúvidas? Veja documentação completa em `COLAB_ECONOMIC_SETUP.md`
