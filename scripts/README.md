# 🔍 Script de Diagnóstico - AI Film Pipeline

## O que faz?

Este script verifica se todo o ambiente está configurado corretamente antes de executar o pipeline de geração de filmes com IA.

## Como usar?

### Opção 1: Script bash (recomendado)
```bash
cd /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP
bash run_diagnostic.sh
```

### Opção 2: Python direto
```bash
cd /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP
python3 scripts/diagnose_system.py
```

## O que é verificado?

1. ✅ **Python Version** - Verifica se Python >= 3.9
2. ✅ **Dependencies** - Valida pacotes críticos (dagster, langchain, langgraph, requests, flask)
3. ✅ **Environment Vars** - Checa GEMINI_API_KEY, COMFYUI_URL, DAGSTER_HOME
4. ✅ **ComfyUI Connection** - Testa se ComfyUI está acessível
5. ✅ **File Structure** - Valida arquivos críticos do projeto
6. ✅ **Dagster Setup** - Verifica instalação do Dagster
7. ✅ **LLM API (Gemini)** - Testa API do Google Gemini
8. ✅ **GitHub Actions** - Valida workflows CI/CD

## Output

O script gera:

1. **Console output** - Relatório visual com status de cada verificação
2. **diagnostic_report.json** - Relatório completo em JSON

### Exemplo de output:

```
🔍 DIAGNÓSTICO DO SISTEMA AI FILM PIPELINE
======================================================================

✅ Python Version
   Python 3.10.12

✅ Dependencies
   dagster: ✅
   langchain: ✅
   langgraph: ✅
   requests: ✅
   flask: ✅

❌ Environment Vars
   GEMINI_API_KEY: ✅ (LLM principal)
   COMFYUI_URL: ❌ (Geração de imagens)
   DAGSTER_HOME: ⚠️  (Orquestração) - opcional

======================================================================
📊 SCORE: 6/8 (75%)
======================================================================

⚠️  Sistema parcialmente configurado
   Corrija os itens abaixo antes de prosseguir

🔧 CORREÇÕES NECESSÁRIAS:
   1. Configurar COMFYUI_URL no .env
   2. ComfyUI inacessível - considerar setup no Hugging Face

📄 Relatório salvo em: diagnostic_report.json
```

## Interpretando o Score

- **80-100%** ✅ Sistema pronto para executar!
- **50-79%** ⚠️  Sistema parcialmente configurado - corrija os itens listados
- **0-49%** ❌ Sistema requer configuração completa

## Próximos passos

### Se score >= 80%
Execute o pipeline completo:
```bash
python scripts/run_end_to_end_test.py
```

### Se score < 80%
Siga as correções sugeridas no output do diagnóstico.

### Se ComfyUI falhar
Configure ComfyUI gratuito no Hugging Face:
```bash
# Guia disponível em:
cat huggingface_setup/README.md
```

## Troubleshooting

### Erro: "Module not found"
```bash
pip install -r requirements.txt
```

### Erro: "GEMINI_API_KEY not found"
Adicione ao arquivo `open3d_implementation/.env`:
```
GEMINI_API_KEY=sua_chave_aqui
```

### Erro: "ComfyUI connection failed"
A URL do Cloudflare Tunnel pode ter expirado. Considere:
1. Reiniciar ComfyUI no Colab
2. Atualizar COMFYUI_URL no .env
3. Configurar ComfyUI permanente no Hugging Face (gratuito)

## Arquivos gerados

- `diagnostic_report.json` - Relatório completo em JSON
- Logs no console

## Suporte

Se encontrar problemas:
1. Execute o diagnóstico
2. Compartilhe o `diagnostic_report.json`
3. Siga as correções sugeridas
