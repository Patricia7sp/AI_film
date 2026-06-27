# 📝 Como Adicionar História ao Notebook do Colab

## 🎯 Problema Identificado

O notebook atual (`colab_automated_notebook.ipynb`) **não tem** o campo para inserir a história que será transformada em filme. Ele apenas:
1. Inicia ComfyUI
2. Cria Cloudflare Tunnel
3. Reporta URL para GitHub

**Falta:** Sistema para enviar a história para o pipeline!

---

## ✅ Solução: Adicionar História ao Notebook

### **Opção 1: História Hardcoded (Mais Simples)**

Adicione esta célula ao notebook **ANTES** de disparar o GitHub Actions:

```python
# ═══════════════════════════════════════════════════════════════════
# 📝 HISTÓRIA PARA O FILME
# ═══════════════════════════════════════════════════════════════════

STORY = """
[COLE SUA HISTÓRIA AQUI]

Exemplo:
Era uma vez, em um reino distante, uma princesa que adorava matemática...
"""

print(f"📖 História carregada: {len(STORY)} caracteres")
```

Depois, **modifique** a célula que dispara o GitHub Actions para incluir a história:

```python
# Modificar esta parte do notebook:
payload = {
    "event_type": "colab-ready",
    "client_payload": {
        "comfyui_url": url,
        "story": STORY,  # ← ADICIONAR ESTA LINHA
        "triggered_by": "colab",
        "timestamp": datetime.now().isoformat()
    }
}
```

---

### **Opção 2: Interface Web (Mais Elegante)**

Use o código do notebook que você mostrou (`colab_comfyui_runner_final.ipynb`):

```python
"""
🎬 COLAB MANAGER COM HISTÓRIA
"""

import os
from google.colab import userdata
from datetime import datetime
import requests
import json

# Config
GITHUB_TOKEN = userdata.get('GITHUB_TOKEN')
GITHUB_REPO = "Patricia7sp/AI_film"
COMFYUI_URL_GIST_ID = userdata.get('COMFYUI_URL_GIST_ID')
COMFYUI_URL = os.getenv("COMFYUI_URL")

# ═══════════════════════════════════════════════════════════════════
# 📝 INSIRA SUA HISTÓRIA AQUI:
# ═══════════════════════════════════════════════════════════════════

STORY = """
O Professor de Matemática

Eu preciso arrumar um jeito de esconder esses gatinhos...
[SUA HISTÓRIA COMPLETA]
"""

# ═══════════════════════════════════════════════════════════════════

class StoryManager:
    def __init__(self):
        self.github_token = GITHUB_TOKEN
        self.github_repo = GITHUB_REPO
        self.gist_id = COMFYUI_URL_GIST_ID
        self.comfyui_url = COMFYUI_URL
        self.story = STORY.strip()
    
    def trigger_github(self):
        """Dispara GitHub Actions com história"""
        print("=" * 70)
        print("🚀 DISPARANDO GITHUB ACTIONS COM HISTÓRIA")
        print("=" * 70)
        
        payload = {
            "event_type": "colab-ready",
            "client_payload": {
                "comfyui_url": self.comfyui_url,
                "story": self.story,
                "story_length": len(self.story),
                "timestamp": datetime.now().isoformat()
            }
        }
        
        url = f"https://api.github.com/repos/{self.github_repo}/dispatches"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            if res.status_code == 204:
                print(f"✅ GitHub Actions disparado!")
                print(f"📖 História: {len(self.story)} caracteres")
                print(f"👀 Acompanhe: https://github.com/{self.github_repo}/actions")
                return True
            else:
                print(f"❌ Erro: {res.status_code}")
                return False
        except Exception as e:
            print(f"❌ Erro: {e}")
            return False
    
    def start(self):
        if not self.comfyui_url:
            print("❌ COMFYUI_URL não definida!")
            return
        
        if not self.story:
            print("❌ História não definida!")
            return
        
        print(f"🔗 ComfyUI: {self.comfyui_url}")
        print(f"📖 História: {len(self.story)} caracteres")
        print("")
        
        self.trigger_github()

# Executar
manager = StoryManager()
manager.start()
```

---

## 🔧 Como Integrar no Notebook Atual

### **Passo 1: Abrir o Notebook**

```bash
# No Colab, abra:
colab_automated_notebook.ipynb
```

### **Passo 2: Adicionar Célula de História**

Adicione uma **nova célula** logo após a célula que captura a URL do Cloudflare:

```python
# ═══════════════════════════════════════════════════════════════════
# 📝 HISTÓRIA PARA O FILME
# ═══════════════════════════════════════════════════════════════════

STORY = """
[COLE SUA HISTÓRIA AQUI]
"""

print(f"📖 História carregada: {len(STORY)} caracteres")

# Salvar história em variável de ambiente
os.environ["STORY"] = STORY
```

### **Passo 3: Modificar Célula do GitHub Actions**

Encontre a célula que tem:

```python
payload = {
    "event_type": "colab-ready",
    "client_payload": {
        "comfyui_url": url,
        ...
    }
}
```

E adicione a história:

```python
payload = {
    "event_type": "colab-ready",
    "client_payload": {
        "comfyui_url": url,
        "story": os.getenv("STORY", ""),  # ← ADICIONAR
        "story_length": len(os.getenv("STORY", "")),  # ← ADICIONAR
        "triggered_by": "colab",
        "timestamp": datetime.now().isoformat()
    }
}
```

---

## 📊 Fluxo Completo Atualizado

```
1. Você abre o notebook no Colab
   ↓
2. Executa todas as células
   ↓
3. ComfyUI inicia
   ↓
4. Cloudflare Tunnel cria URL
   ↓
5. Você cola a HISTÓRIA na célula
   ↓
6. GitHub Actions é disparado COM a história
   ↓
7. Pipeline processa:
   - Analisa história
   - Gera prompts
   - Cria imagens no ComfyUI
   - Gera áudio
   - Compila vídeo
   ↓
8. Filme pronto! 🎬
```

---

## ✅ Checklist

- [ ] Adicionar célula de história no notebook
- [ ] Modificar payload do GitHub Actions
- [ ] Testar com história de exemplo
- [ ] Verificar se história chega no workflow
- [ ] Validar geração de imagens

---

## 🐛 Troubleshooting

### **História não chega no workflow**

Verifique nos logs do GitHub Actions se o `client_payload` contém a história:

```yaml
# No workflow, adicione debug:
- name: Debug Payload
  run: |
    echo "Story length: ${{ github.event.client_payload.story_length }}"
    echo "Story preview: ${{ github.event.client_payload.story }}" | head -c 100
```

### **História muito grande**

GitHub Actions tem limite de payload. Se a história for muito grande (>10KB), considere:

1. Salvar história em um Gist
2. Enviar apenas o Gist ID no payload
3. Workflow baixa história do Gist

---

## 📚 Referências

- Notebook original: `colab_automated_notebook.ipynb`
- Notebook com história: `colab_comfyui_runner_final.ipynb` (seu exemplo)
- Workflow: `.github/workflows/full-auto-colab-pipeline.yml`

---

**Próximo passo:** Modificar o notebook atual para incluir a história! 🚀
