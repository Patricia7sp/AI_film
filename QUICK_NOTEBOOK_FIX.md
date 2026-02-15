# ⚡ Modificação Rápida do Notebook - Adicionar História

## 🎯 Objetivo
Adicionar campo de história ao notebook `colab_automated_notebook.ipynb`

---

## 📝 PASSO 1: Adicionar Célula de História

**Localização:** Logo após a célula de "Install ComfyUI"

**Código para adicionar:**

```python
#@title 📝 HISTÓRIA PARA O FILME
# ═══════════════════════════════════════════════════════════════════
# COLE SUA HISTÓRIA AQUI:
# ═══════════════════════════════════════════════════════════════════

STORY = """
Era uma vez, em um reino distante, uma princesa que adorava matemática.
Ela passava seus dias resolvendo equações e criando teoremas.
Um dia, descobriu um padrão mágico nos números que mudaria tudo...
"""

print("="*60)
print("📖 HISTÓRIA CARREGADA")
print("="*60)
print(f"Caracteres: {len(STORY)}")
print(f"Palavras: {len(STORY.split())}")
print(f"Linhas: {len(STORY.splitlines())}")
print("="*60)
print()

# Salvar em variável de ambiente
import os
os.environ['STORY'] = STORY.strip()
```

---

## 🔧 PASSO 2: Modificar Célula do GitHub Actions

**Encontre esta parte no notebook:**

```python
def report_to_github(url):
    """Reporta URL para GitHub Gist automaticamente"""
    ...
    gist_data = {
        "description": "ComfyUI URL - Auto-reported from Colab",
        "public": False,
        "files": {
            "comfyui_url.json": {
                "content": json.dumps({
                    "url": url,
                    "updated_at": datetime.now().isoformat(),
                    ...
```

**Modifique para:**

```python
def report_to_github(url):
    """Reporta URL + História para GitHub Gist automaticamente"""
    ...
    # Pegar história do ambiente
    story = os.getenv('STORY', '')
    
    gist_data = {
        "description": "ComfyUI URL + Story - Auto-reported from Colab",
        "public": False,
        "files": {
            "comfyui_url.json": {
                "content": json.dumps({
                    "url": url,
                    "story": story,  # ← ADICIONAR
                    "story_length": len(story),  # ← ADICIONAR
                    "updated_at": datetime.now().isoformat(),
                    ...
```

---

## ✅ PASSO 3: Testar

1. Abra o notebook no Colab
2. Execute todas as células
3. Verifique se a história foi carregada
4. Confirme que o GitHub Actions recebeu a história

---

## 🎬 Fluxo Final

```
1. Executar notebook
   ↓
2. Célula de história carrega texto
   ↓
3. ComfyUI inicia
   ↓
4. Cloudflare cria URL
   ↓
5. História + URL enviados para Gist
   ↓
6. GitHub Actions disparado
   ↓
7. Pipeline processa história
   ↓
8. Filme gerado! 🎉
```

---

## 📊 Verificação

No GitHub Actions, você deve ver:

```yaml
client_payload:
  comfyui_url: "https://..."
  story: "Era uma vez..."
  story_length: 150
```

---

**Tempo estimado:** 5 minutos  
**Dificuldade:** Fácil (copiar/colar)

---

## 🆘 Se Tiver Problemas

Execute o diagnóstico:
```bash
python3 scripts/diagnose_system.py
```

Score atual: **88% (7/8)** ✅
