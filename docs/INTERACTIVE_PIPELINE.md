# 🎬 Pipeline Interativo - Guia de Uso

## 📋 Visão Geral

Sistema interativo que abre automaticamente interfaces web para:
1. **Flask UI** - Inserir história
2. **Dagster UI** - Monitorar execução

---

## 🚀 Como Usar

### **Método 1: Script Interativo (Recomendado)**

```bash
# 1. Certifique-se que ComfyUI está rodando
# URL exemplo: https://profiles-dem-burns-chronicle.trycloudflare.com

# 2. Configure a URL do ComfyUI
export COMFYUI_URL="https://sua-url.trycloudflare.com"

# 3. Execute o script interativo
python .github/scripts/interactive_pipeline.py
```

**O que acontece:**
1. ✅ Verifica se ComfyUI está acessível
2. 🌐 Inicia Flask server (porta 5001)
3. 📊 Inicia Dagster UI (porta 3000)
4. 🌐 Abre automaticamente 2 tabs no navegador:
   - **Tab 1:** Flask UI para inserir história
   - **Tab 2:** Dagster UI para monitorar
5. ⏳ Aguarda você inserir a história
6. 🚀 Executa o pipeline automaticamente

---

### **Método 2: Manual (Passo a Passo)**

#### **Passo 1: Iniciar Flask**

```bash
# Criar e executar Flask app
python -c "
from flask import Flask, request, render_template_string
app = Flask(__name__)

@app.route('/')
def index():
    return '''
    <html>
    <body>
        <h1>AI Film - Story Input</h1>
        <form method=POST action=/submit>
            <textarea name=story rows=10 cols=50></textarea><br>
            <button type=submit>Submit</button>
        </form>
    </body>
    </html>
    '''

@app.route('/submit', methods=['POST'])
def submit():
    story = request.form['story']
    with open('output/story_latest.txt', 'w') as f:
        f.write(story)
    return 'Story saved!'

app.run(port=5001)
"
```

#### **Passo 2: Iniciar Dagster**

```bash
# Em outro terminal
dagster dev -f orchestration/enhanced_dagster_pipeline.py -p 3000
```

#### **Passo 3: Abrir Navegador**

```bash
# Abrir Flask UI
open http://localhost:5001

# Abrir Dagster UI
open http://localhost:3000
```

#### **Passo 4: Inserir História**

1. Acesse http://localhost:5001
2. Digite sua história
3. Clique em "Submit"

#### **Passo 5: Monitorar Execução**

1. Acesse http://localhost:3000
2. Veja o pipeline executando em tempo real

---

## 🎨 Flask UI - Interface

### **Recursos:**

- ✅ **Editor de texto** com contador de caracteres
- ✅ **Exemplos** de histórias
- ✅ **Validação** de input
- ✅ **Feedback visual** (sucesso/erro)
- ✅ **Links rápidos** para Dagster e ComfyUI

### **Screenshot:**

```
┌─────────────────────────────────────────┐
│  🎬 AI Film Generator                   │
│  Insira sua história para gerar o filme │
├─────────────────────────────────────────┤
│  💡 Exemplos de histórias:              │
│  • Uma jornada épica através de um      │
│    mundo cyberpunk futurista            │
│  • A história de um robô que descobre   │
│    emoções humanas                      │
├─────────────────────────────────────────┤
│  📝 Sua História:                       │
│  ┌─────────────────────────────────┐   │
│  │ Era uma vez...                  │   │
│  │                                 │   │
│  │                                 │   │
│  └─────────────────────────────────┘   │
│  0 caracteres                           │
├─────────────────────────────────────────┤
│  [ 🚀 Gerar Filme ]  [ 🗑️ Limpar ]     │
├─────────────────────────────────────────┤
│  📊 Dagster UI  |  🎨 ComfyUI          │
└─────────────────────────────────────────┘
```

---

## 📊 Dagster UI - Monitoramento

### **O que você vê:**

1. **Pipeline Overview**
   - Status geral
   - Tempo de execução
   - Progresso

2. **Assets**
   - `enhanced_multimodal_input_asset`
   - `enhanced_langgraph_workflow_asset`

3. **Logs em Tempo Real**
   - Cada etapa do pipeline
   - Erros e avisos
   - Métricas

4. **Resultados**
   - Imagens geradas
   - Áudios criados
   - Vídeo final

---

## 🔧 Configuração

### **Variáveis de Ambiente:**

```bash
# ComfyUI URL (obrigatório)
export COMFYUI_URL="https://sua-url.trycloudflare.com"

# Portas (opcional)
export FLASK_PORT=5001
export DAGSTER_PORT=3000

# LLM (opcional - padrão: Gemini)
export GEMINI_API_KEY="sua_chave"
export DEFAULT_LLM="gemini-2.0-flash-exp"
```

### **Arquivo de História:**

O sistema salva a história em:
```
output/story_latest.txt
```

O pipeline lê automaticamente deste arquivo se nenhuma história for fornecida via parâmetro.

---

## 🐛 Troubleshooting

### **Erro: "ComfyUI não está disponível"**

**Causa:** ComfyUI não está rodando ou URL incorreta

**Solução:**
```bash
# Verificar URL
curl https://sua-url.trycloudflare.com

# Atualizar variável
export COMFYUI_URL="https://url-correta.trycloudflare.com"
```

### **Erro: "ValueError: Nenhuma história fornecida"**

**Causa:** Arquivo `output/story_latest.txt` não existe

**Solução:**
```bash
# Criar diretório
mkdir -p output

# Criar história de teste
echo "Era uma vez em um mundo distante..." > output/story_latest.txt
```

### **Erro: "Port 5001 already in use"**

**Causa:** Flask já está rodando

**Solução:**
```bash
# Matar processo
lsof -ti:5001 | xargs kill -9

# Ou usar outra porta
export FLASK_PORT=5002
```

### **Erro: "Dagster não encontrado"**

**Causa:** Dagster não instalado

**Solução:**
```bash
pip install dagster dagster-webserver
```

---

## 📝 Fluxo Completo

```
┌─────────────────────────────────────────────────────────────┐
│                    1. ComfyUI Ativo                         │
│                           ↓                                 │
│              2. Script Detecta ComfyUI OK                   │
│                           ↓                                 │
│         ┌─────────────────┴─────────────────┐              │
│         ↓                                   ↓              │
│   3. Inicia Flask              4. Inicia Dagster           │
│   (porta 5001)                 (porta 3000)                │
│         ↓                                   ↓              │
│   5. Abre Tab 1                6. Abre Tab 2               │
│   (Flask UI)                   (Dagster UI)                │
│         ↓                                                   │
│   7. Usuário Insere História                               │
│         ↓                                                   │
│   8. História Salva em output/story_latest.txt             │
│         ↓                                                   │
│   9. Pipeline Detecta História                             │
│         ↓                                                   │
│   10. Pipeline Executa                                     │
│         ↓                                                   │
│   11. Usuário Monitora no Dagster UI                       │
│         ↓                                                   │
│   12. Resultado: Filme Gerado! 🎬                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Vantagens

### **Antes (Sem Interface):**
- ❌ Erro: "Nenhuma história fornecida"
- ❌ Precisa editar código para adicionar história
- ❌ Difícil de monitorar progresso
- ❌ Sem feedback visual

### **Agora (Com Interface):**
- ✅ Interface web bonita e intuitiva
- ✅ Inserir história facilmente
- ✅ Monitoramento em tempo real
- ✅ Feedback visual claro
- ✅ Links rápidos para todas as ferramentas

---

## 🚀 Integração com GitHub Actions

### **Workflow Atualizado:**

```yaml
- name: 🎬 Run AI Film Pipeline
  env:
    COMFYUI_URL: ${{ needs.orchestrate-colab.outputs.comfyui_url }}
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
  run: |
    # Criar história padrão se não existir
    mkdir -p output
    if [ ! -f output/story_latest.txt ]; then
      echo "Uma jornada épica através de um mundo cyberpunk futurista" > output/story_latest.txt
    fi
    
    # Executar pipeline
    python .github/scripts/execute_dagster_pipeline.py \
      --comfyui-url $COMFYUI_URL
```

---

## 📚 Exemplos de Histórias

### **Sci-Fi:**
```
Em 2157, a humanidade descobriu portais para dimensões paralelas. 
Um cientista corajoso embarca em uma jornada para encontrar uma 
civilização perdida que pode salvar a Terra da extinção.
```

### **Fantasia:**
```
No reino de Eldoria, um jovem aprendiz de mago descobre um antigo 
grimório que revela segredos sobre a origem da magia. Sua jornada 
para dominar esses poderes mudará o destino de todos os reinos.
```

### **Cyberpunk:**
```
Neo-Tokyo, 2089. Uma hacker rebelde descobre uma conspiração 
corporativa que ameaça a liberdade de milhões. Ela deve infiltrar 
a megacorporação mais poderosa do mundo para expor a verdade.
```

---

## 🎨 Personalização

### **Customizar Flask UI:**

Edite o template HTML em `.github/scripts/interactive_pipeline.py`:

```python
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Seu Título</title>
    <style>
        /* Seus estilos aqui */
    </style>
</head>
<body>
    <!-- Seu HTML aqui -->
</body>
</html>
"""
```

### **Adicionar Validações:**

```python
@app.route('/submit', methods=['POST'])
def submit():
    story = request.form['story']
    
    # Validação customizada
    if len(story) < 50:
        return jsonify({'error': 'História muito curta'}), 400
    
    if len(story) > 5000:
        return jsonify({'error': 'História muito longa'}), 400
    
    # Salvar...
```

---

## 📊 Métricas e Logs

### **Flask Logs:**
```
🌐 Flask rodando em http://localhost:5001
✅ História salva: output/story_20251103_095800.txt
📊 Caracteres: 1234
```

### **Dagster Logs:**
```
🚀 Iniciando pipeline...
📦 Materializando assets...
✅ Asset de input executado com sucesso!
📋 Story processada: 1234 caracteres
🔄 Executando workflow LangGraph...
✅ Workflow LangGraph executado!
📊 RESULTADOS DO PIPELINE:
   ✅ Cenas processadas: 8
   ✅ Imagens geradas: 8
   ✅ Áudios gerados: 8
   ✅ Vídeo: output/video_final.mp4
```

---

**Data:** 3 de Novembro de 2025  
**Versão:** 1.0  
**Status:** ✅ Implementado
