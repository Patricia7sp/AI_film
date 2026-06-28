# 🚀 Setup ComfyUI no RunPod Serverless

**GPU sob demanda | Cobrança por segundo | Escala a zero entre chamadas**

> ✅ **Caminho atual.** Substitui Colab + Cloudflare + Gist e a tentativa
> de Hugging Face Spaces (que deixou de oferecer GPU gratuita para apps
> Docker). O pipeline (`langgraph_adapter.py`, função `generate_images`)
> já chama a API serverless do RunPod via `RUNPOD_API_KEY` e
> `RUNPOD_ENDPOINT_ID`. Sem essas duas variáveis no `.env`, ele cai
> direto no fallback mock — não há mais chamada a uma URL `COMFYUI_URL`.

## Por que RunPod Serverless?

- ✅ Worker oficial mantido para ComfyUI: [runpod-workers/worker-comfyui](https://github.com/runpod-workers/worker-comfyui)
- ✅ Cobra por segundo de execução real (não pelo tempo que o servidor fica ligado)
- ✅ Escala a zero entre chamadas — sem custo de "GPU ociosa esperando"
- ✅ T4 ≈ $0.40/h equivalente, mas só durante a geração real (segundos, não horas)
- ⚠️ Cold start: a primeira chamada após um período ocioso pode levar de alguns
  segundos a ~1 minuto além do tempo de geração, porque o worker precisa subir

## Setup passo a passo

### PASSO 1: Conta e API Key

1. Crie conta em https://www.runpod.io
2. Settings → API Keys → criar uma nova key
3. Guarde a key — vai virar `RUNPOD_API_KEY` no `.env`

### PASSO 2: Build da imagem customizada

A imagem `runpod/worker-comfyui:5.8.6-base` não vem com nenhum checkpoint. O
Dockerfile em `runpod_worker/Dockerfile` (neste repositório) baixa o
checkpoint SD1.5 (`v1-5-pruned-emaonly.safetensors`, ~4GB) por cima da
imagem base oficial.

Valide o setup local antes do build:

```bash
python3 scripts/validate_runpod_setup.py
```

Build e push para um registry que o RunPod consiga puxar (Docker Hub, GHCR, etc.):

```bash
cd runpod_worker
docker build -t SEU_USUARIO/comfyui-ai-film-pipeline:latest .
docker push SEU_USUARIO/comfyui-ai-film-pipeline:latest
```

Ou use o wrapper do repositório, que encontra o Docker CLI interno do Docker Desktop quando `docker` não está no PATH:

```bash
scripts/build_runpod_worker.sh SEU_USUARIO/comfyui-ai-film-pipeline:latest
```

### PASSO 3: Criar o endpoint Serverless

1. RunPod Console → Serverless → New Endpoint
2. **Container Image:** `SEU_USUARIO/comfyui-ai-film-pipeline:latest`
3. **GPU:** NVIDIA T4 (mais barata; suficiente para SD1.5)
4. **Workers:** Min 0 (essencial para escalar a zero), Max conforme seu volume
5. **Idle Timeout:** alguns segundos (controla quanto tempo o worker fica de
   pé entre o fim de um job e o desligamento — quanto menor, menos custo
   ocioso, mas mais cold starts se as chamadas forem espaçadas)
6. Criar e copiar o **Endpoint ID** exibido no painel

### PASSO 4: Configurar o `.env`

```bash
RUNPOD_API_KEY=sua_api_key
RUNPOD_ENDPOINT_ID=seu_endpoint_id
```

### PASSO 5: Testar

```bash
curl -X POST "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": {"workflow": {}}}'
```

(Um workflow vazio deve retornar erro de validação do ComfyUI, não erro de
autenticação — isso já confirma que a key e o endpoint estão certos.)

O mesmo teste pode ser feito sem imprimir segredos:

```bash
python3 scripts/validate_runpod_setup.py --test-endpoint
```

Depois, rode o pipeline normalmente; `generate_images()` em
`open3d_implementation/core/langgraph_adapter.py` faz o resto.

## Formato da API (referência)

- **Request:** `POST https://api.runpod.ai/v2/{endpoint_id}/run`
  com `{"input": {"workflow": <workflow ComfyUI no formato API>}}`
- **Polling:** `GET https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}`
- **Resultado:** `output.images[0].data` é a imagem em base64 (PNG)

## Custos (estimativa para uso intermitente automatizado)

Para ~10 gerações/dia, ~30-60s de GPU ativa cada (após o cold start
inicial do dia): algo na faixa de **$5-15/mês**, bem abaixo de manter
qualquer hardware sempre ligado. Acompanhe o uso real no painel do RunPod
nas primeiras semanas e ajuste o Idle Timeout se os cold starts pesarem
demais na experiência.

## Troubleshooting

- **Erro de autenticação:** confira `RUNPOD_API_KEY` e se o endpoint não
  foi pausado/deletado.
- **Job fica em `IN_QUEUE` por muito tempo:** workers Max pode estar
  esgotado, ou a região/disponibilidade de T4 está escassa no momento.
- **`CheckpointLoaderSimple` falha:** o build do Dockerfile não baixou o
  checkpoint corretamente — rebuild e confira `models/checkpoints/` dentro
  da imagem.
