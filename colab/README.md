# 🎬 Colab Manager com Flask UI

## 📋 Novo Fluxo Integrado

```
1. Você abre Colab
2. ComfyUI inicia
3. URL publicada no Gist
4. 🆕 FLASK UI ABRE AUTOMATICAMENTE (pop-up)
5. Você insere a história
6. História salva
7. 🆕 DEPOIS GitHub Actions é disparado
8. Pipeline executa com a história
9. Monitora inatividade
10. Auto-shutdown
```

---

## 🚀 Como Usar no Colab

### **1. Instalar Dependências**

```python
# No início do seu notebook Colab
!pip install flask flask-ngrok pyngrok -q
```

### **2. Copiar o Código**

Copie o conteúdo de `colab_with_flask_ui.py` para uma célula do Colab.

### **3. Configurar Secrets**

No Colab, configure os secrets:
- `GITHUB_TOKEN`
- `COMFYUI_URL_GIST_ID`

### **4. Executar**

```python
# Após ComfyUI iniciar, defina a URL
import os
os.environ['COMFYUI_URL'] = "https://sua-url.trycloudflare.com"

# Execute o manager
# (o código já está configurado para rodar automaticamente)
```

---

## 🎯 Diferenças do Código Original

| Original | Novo (com Flask) |
|----------|------------------|
| Dispara GitHub Actions imediatamente | ✅ Abre Flask UI primeiro |
| Sem input de história | ✅ Aguarda história ser inserida |
| Pipeline pode falhar sem história | ✅ História garantida antes do pipeline |

---

## 📝 Exemplo Completo no Colab

```python
# ═══════════════════════════════════════════════════════
# CÉLULA 1: Instalar Dependências
# ═══════════════════════════════════════════════════════
!pip install flask flask-ngrok pyngrok -q

# ═══════════════════════════════════════════════════════
# CÉLULA 2: Configurar ComfyUI
# ═══════════════════════════════════════════════════════
# ... seu código de inicialização do ComfyUI ...

# ═══════════════════════════════════════════════════════
# CÉLULA 3: Colab Manager com Flask UI
# ═══════════════════════════════════════════════════════
import time, threading, requests, json, os
from datetime import datetime
from IPython.display import display, HTML, Javascript
from google.colab import userdata
from flask import Flask, request, jsonify, render_template_string
from flask_ngrok import run_with_ngrok

# ... (copie todo o código de colab_with_flask_ui.py aqui) ...

# ═══════════════════════════════════════════════════════
# CÉLULA 4: Definir ComfyUI URL e Iniciar
# ═══════════════════════════════════════════════════════
os.environ['COMFYUI_URL'] = "https://sua-url.trycloudflare.com"

manager = ColabManager()
manager.start()

# Agora:
# 1. Flask UI abrirá automaticamente
# 2. Insira sua história
# 3. GitHub Actions será disparado
# 4. Acompanhe em: https://github.com/Patricia7sp/AI_film/actions
```

---

## 🌐 Flask UI - O que Acontece

1. **Flask inicia** em thread separada
2. **ngrok** expõe Flask publicamente
3. **Pop-up abre** automaticamente com link
4. **Você insere** a história
5. **História salva** em memória
6. **GitHub Actions** disparado com a história

---

## 🔧 Personalização

### **Mudar Timeout da História**

```python
# No código, linha ~wait_for_story
story = self.wait_for_story(timeout_min=15)  # 15 minutos
```

### **Desabilitar Auto-Open**

```python
# Comentar esta linha:
# display(Javascript(f'window.open("{self.flask_url}", "_blank");'))
```

### **Adicionar Validação de História**

```python
@app.route('/submit', methods=['POST'])
def submit():
    story = request.get_json().get('story', '').strip()
    
    # Validações customizadas
    if len(story) < 50:
        return jsonify({'success': False, 'error': 'Muito curta'}), 400
    
    if len(story) > 5000:
        return jsonify({'success': False, 'error': 'Muito longa'}), 400
    
    # ... resto do código
```

---

## 📊 Integração com GitHub Actions

O GitHub Actions receberá a história no payload:

```yaml
# No workflow .github/workflows/full-auto-colab-pipeline.yml

- name: 🎬 Run AI Film Pipeline
  env:
    COMFYUI_URL: ${{ github.event.client_payload.comfyui_url }}
    STORY_INPUT: ${{ github.event.client_payload.story }}
  run: |
    # Salvar história em arquivo
    echo "$STORY_INPUT" > output/story_latest.txt
    
    # Executar pipeline
    python .github/scripts/execute_dagster_pipeline.py
```

---

## 🐛 Troubleshooting

### **Flask não abre automaticamente**

**Solução:** Clique manualmente no link exibido no Colab

### **ngrok URL não obtida**

**Solução:** Verifique em http://localhost:4040 e copie a URL manualmente

### **História não chega no GitHub Actions**

**Solução:** Verifique os logs do Colab para confirmar que `story_data['submitted'] = True`

---

## 💡 Vantagens desta Abordagem

✅ **Integrado no Colab** - Não precisa de script separado  
✅ **Fluxo natural** - Flask → História → GitHub Actions  
✅ **Menos erros** - História garantida antes do pipeline  
✅ **Melhor UX** - Pop-up automático  
✅ **Código limpo** - Versão concisa (~150 linhas)

---

## 🎯 Próximos Passos

1. ✅ Copie o código para seu Colab
2. ✅ Configure os secrets
3. ✅ Execute e teste
4. ✅ Insira uma história de teste
5. ✅ Verifique GitHub Actions

---

**Data:** 3 de Novembro de 2025  
**Status:** ✅ Pronto para uso no Colab
