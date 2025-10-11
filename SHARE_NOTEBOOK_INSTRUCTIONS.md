# 📋 Instruções: Compartilhar Notebook com Service Account

## ✅ Service Account Criado!

**Email do Service Account:**
```
colab-automation@ia-video-460518.iam.gserviceaccount.com
```

**Projeto:** `ia-video-460518`

---

## 🎯 Passo a Passo para Compartilhar o Notebook

### **1. Abrir o Notebook no Google Colab**

1. Acesse: https://colab.research.google.com/
2. Abra seu notebook (ou faça upload do `colab_automated_notebook.ipynb`)
3. O notebook deve estar no seu Google Drive

### **2. Obter o ID do Notebook**

1. Com o notebook aberto no Colab, veja a URL:
   ```
   https://colab.research.google.com/drive/XXXXX-NOTEBOOK-ID-XXXXX
   ```

2. Copie o ID (a parte depois de `/drive/`)

3. **Configure o secret** (se ainda não tiver):
   ```bash
   gh secret set COLAB_NOTEBOOK_ID --body "XXXXX-SEU-NOTEBOOK-ID-XXXXX"
   ```

### **3. Compartilhar com Service Account**

**Opção A: Via Interface do Colab**

1. No notebook aberto, clique em **"Share"** (canto superior direito)
2. Cole o email:
   ```
   colab-automation@ia-video-460518.iam.gserviceaccount.com
   ```
3. Selecione permissão: **"Editor"**
4. **DESMARQUE** "Notify people" (não precisa enviar email)
5. Clique em **"Share"**

**Opção B: Via Google Drive**

1. Abra o Google Drive: https://drive.google.com/
2. Encontre o arquivo `.ipynb` do notebook
3. Clique com botão direito → **"Share"**
4. Cole o email:
   ```
   colab-automation@ia-video-460518.iam.gserviceaccount.com
   ```
5. Permissão: **"Editor"**
6. **DESMARQUE** "Notify people"
7. Clique em **"Share"**

---

## ✅ Verificação

Depois de compartilhar, verifique:

1. **O notebook está compartilhado:**
   - Abra o notebook no Colab
   - Veja se aparece "Shared" ou ícone de compartilhamento

2. **Secrets configurados:**
   ```bash
   gh secret list | grep -E "(GOOGLE|COLAB)"
   ```
   
   Deve mostrar:
   ```
   ✅ GOOGLE_COLAB_CREDENTIALS
   ✅ COLAB_NOTEBOOK_ID
   ```

---

## 🚀 Testar Automação

Depois de compartilhar:

```bash
# Executar workflow do pipeline completo
gh workflow run "full-auto-colab-pipeline.yml"

# Acompanhar
gh run watch
```

---

## 📝 Checklist

- [ ] Service Account criado (`colab-automation@ia-video-460518.iam.gserviceaccount.com`)
- [ ] Chave JSON gerada e configurada no secret
- [ ] Notebook aberto no Google Colab
- [ ] ID do notebook copiado
- [ ] COLAB_NOTEBOOK_ID configurado no GitHub
- [ ] Notebook compartilhado com service account (permissão "Editor")
- [ ] Secrets verificados
- [ ] Pronto para testar!

---

## 🆘 Problemas?

### **"Não consigo encontrar o notebook ID"**

O ID está na URL quando você abre o notebook:
```
https://colab.research.google.com/drive/1a2b3c4d5e6f7g8h9i0j
                                    ^^^^^^^^^^^^^^^^^^^^
                                    Este é o ID
```

### **"Service account não tem acesso"**

Verifique:
1. Email está correto
2. Permissão é "Editor" (não "Viewer")
3. Notebook está no Google Drive (não local)

### **"Secrets não aparecem"**

Execute:
```bash
gh secret set GOOGLE_COLAB_CREDENTIALS --body "$(cat colab-automation-key-base64.txt)"
```

---

## 📞 Próximo Passo

**Depois de compartilhar o notebook, me avise e vamos testar a automação completa!** 🚀
