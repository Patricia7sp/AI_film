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

### PASSO 2: Carregar modelos Hugging Face no RunPod sem Docker Desktop

**Caminho recomendado para trocar modelos:** use um **RunPod Network Volume**
persistente e carregue os checkpoints direto do Hugging Face para o volume.
Assim, o endpoint Serverless usa o mesmo volume em `/runpod-volume` e não é
necessário fazer build local, abrir Docker Desktop ou subir uma nova imagem a
cada troca de modelo.

1. RunPod Console → Storage → Network Volumes → criar um volume na mesma região
   do endpoint Serverless.
2. Criar um Pod temporário simples com esse volume anexado.
3. Abrir o terminal do Pod e baixar o checkpoint direto no volume:

```bash
export HF_TOKEN=seu_token_huggingface_se_o_modelo_exigir

bash scripts/runpod_download_hf_model.sh \
  semantic-sdxl \
  "ai-film-semantic-juggernaut-xl.safetensors"
```

O alias `semantic-sdxl` baixa:

```text
https://huggingface.co/RunDiffusion/Juggernaut-XL-v9/resolve/main/Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors
```

Se você estiver copiando o script manualmente para o Pod, o caminho final deve
ficar assim:

```bash
/workspace/models/checkpoints/ai-film-semantic-juggernaut-xl.safetensors
```

No worker Serverless com volume anexado, o mesmo arquivo fica disponível em:

```bash
/runpod-volume/models/checkpoints/ai-film-semantic-juggernaut-xl.safetensors
```

Configure o `.env` local para apontar o workflow para esse checkpoint:

```bash
IMAGE_GENERATION_PROVIDER=comfyui
COMFYUI_DEFAULT_CHECKPOINT=ai-film-semantic-juggernaut-xl.safetensors
COMFYUI_CHECKPOINT_COMIC_STORYBOOK=ai-film-semantic-juggernaut-xl.safetensors
```

### PASSO 2A.1: FLUX.2 Klein Base 4B (tier semântico principal)

O tier principal em validação é o FLUX.2 Klein Base 4B. Ele usa pesos Apache
2.0, suporta text-to-image e edição multi-referência nativa e fica no Network
Volume, sem Docker Desktop local:

```bash
bash scripts/runpod_prepare_flux2_volume.sh
```

Arquivos esperados:

```text
models/diffusion_models/flux-2-klein-base-4b.safetensors
models/text_encoders/qwen_3_4b.safetensors
models/vae/flux2-vae.safetensors
```

Não altere o endpoint principal durante o download ou no primeiro boot. Crie
um endpoint temporário com a imagem `flux2-klein-COMMIT_SHA`, execute:

```bash
COMFYUI_FLUX2_SMOKE_ENDPOINT_ID=ENDPOINT_TEMPORARIO \
python scripts/smoke_comfyui_flux2_klein.py
```

Somente após o smoke semântico e a revisão humana, ative:

```bash
COMFYUI_MODEL_FAMILY=flux2_klein
```

`COMFYUI_MODEL_FAMILY=sdxl` preserva o rollback para Juggernaut/Animagine,
ControlNet e IP-Adapter. O controle nativo multi-referência do FLUX.2 deve ser
ativado em uma etapa separada depois que o text-to-image passar o gate.

**Modelo inicial recomendado:** `Juggernaut XL v9`, salvo no volume como
`ai-film-semantic-juggernaut-xl.safetensors`. Ele é um checkpoint SDXL em arquivo
único (`.safetensors`) e entra como baseline semantic-first: primeiro a cena
precisa obedecer personagens, objetos e enquadramento; o estilo de quadrinhos
entra por prompt/refino sem sacrificar aderência narrativa.

O alias legado `comic-sdxl` continua disponível para baixar `Animagine XL 4.0
Opt` como `ai-film-comic-storybook-xl.safetensors`, mas ele não deve ser o
default para cenas com objetos pequenos ou múltiplos requisitos narrativos.

Para testar um checkpoint mais ilustrativo/animation-first, carregue também:

```bash
bash scripts/runpod_download_hf_model.sh \
  animation-sdxl \
  "ai-film-dreamshaper-xl-turbo-sfw.safetensors"
```

Esse alias baixa `Lykon/dreamshaper-xl-v2-turbo` e deve ser testado com poucos
steps e CFG baixo, por ser um checkpoint Turbo.

Para preparar o próximo fluxo controlado de objetos pequenos, carregue também
os modelos ControlNet SDXL no mesmo Network Volume:

```bash
bash scripts/runpod_prepare_controlnet_volume.sh
```

Esse script baixa `controlnet-sdxl-canny` e `controlnet-sdxl-depth`, valida os
arquivos e lista o conteúdo final em `/runpod-volume/models/controlnet/` ou
`/workspace/models/controlnet/`, conforme o volume montado no Pod temporário.

Para preparar o controle de identidade e objetos por referência, execute no
mesmo Pod temporário, sem Docker Desktop local:

```bash
bash scripts/runpod_prepare_ipadapter_volume.sh
```

O comando baixa o IP-Adapter Plus SDXL e o encoder CLIP ViT-H diretamente do
Hugging Face para o Network Volume. A imagem do worker inclui o custom node
oficial `comfyorg/comfyui-ipadapter` fixado por commit; o wrapper liga
`models/ipadapter` e `models/clip_vision` ao ComfyUI durante o boot.
O wrapper `/start_ai_film.sh` faz o link para `/comfyui/models/controlnet/` no
boot do worker Serverless.

Se o Pod temporário não tiver este repositório clonado, gere localmente um
comando autônomo para colar no terminal web do Pod:

```bash
python3 scripts/print_runpod_controlnet_install_command.py
```

Também existe automação via GraphQL para criar um Pod temporário, executar o
download com `status.json` em HTTP e terminar o Pod depois:

```bash
python3 scripts/runpod_controlnet_pod.py create --gpu-type-id "NVIDIA RTX A4000"
python3 scripts/runpod_controlnet_pod.py list
python3 scripts/runpod_controlnet_pod.py terminate --pod-id POD_ID
```

Não baixe checkpoints grandes no `dockerArgs` do endpoint Serverless. O
download bloqueia o bootstrap do handler e pode deixar o worker `unhealthy`.
Use um Pod temporário com terminal web ou outro processo separado para popular
o Network Volume antes de ligar o endpoint.

### PASSO 2B: Build da imagem customizada (fallback)

A imagem FLUX.2 usa `runpod/worker-comfyui:5.8.6-base` para disponibilizar os
nodes core do workflow Klein. Essa imagem deve ser validada primeiro em um
endpoint canário L4/Ada/Ampere; não substitua o endpoint SDXL em GPUs antigas
que falharam no pre-flight de driver. O Dockerfile
em `runpod_worker/Dockerfile` (neste repositório) baixa um
checkpoint realista para produção cinematográfica
(`ai-film-cinematic-realism.safetensors`) e mantém SD1.5
(`v1-5-pruned-emaonly.safetensors`) apenas como fallback legado. Não use SD1.5
como checkpoint principal para o pipeline final: ele falha em coerência de
estilo, personagem e fidelidade visual.

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

O caminho recomendado não exige Docker local: após merge em `main`, o workflow
`Build RunPod ComfyUI Worker` constrói `runpod_worker/` no GitHub Actions e
publica duas tags no GitHub Container Registry (GHCR), usando apenas o
`GITHUB_TOKEN` efêmero do próprio workflow:

```text
ghcr.io/patricia7sp/ai-film-comfyui-worker:flux2-klein-latest
ghcr.io/patricia7sp/ai-film-comfyui-worker:flux2-klein-COMMIT_SHA
```

Use a tag com SHA no release do endpoint RunPod para deploy reproduzível. A tag
`latest` serve apenas para inspeção e smoke test, não para fixar produção.
Na primeira publicação, abra as configurações do pacote
`ai-film-comfyui-worker` no GitHub e altere a visibilidade para `Public`. O
`GITHUB_TOKEN` do workflow pode publicar a imagem, mas não tem permissão para
alterar essa configuração da conta.

Tag validada em produção no endpoint atual:

```text
151113/comfyui-ai-film-pipeline:storybook-volume-20260707
```

Ou use o wrapper do repositório, que encontra o Docker CLI interno do Docker Desktop quando `docker` não está no PATH:

```bash
scripts/build_runpod_worker.sh SEU_USUARIO/comfyui-ai-film-pipeline:latest
```

Para testar outro checkpoint sem editar o Dockerfile:

```bash
RUNPOD_COMFYUI_BASE_IMAGE=runpod/worker-comfyui:5.8.5-base \
AI_FILM_CHECKPOINT_NAME=meu-checkpoint.safetensors \
AI_FILM_CHECKPOINT_URL=https://huggingface.co/org/model/resolve/main/model.safetensors \
scripts/build_runpod_worker.sh SEU_USUARIO/comfyui-ai-film-pipeline:latest
```

Use este caminho apenas quando precisar instalar custom nodes, Python packages
ou bibliotecas de sistema. Para trocar apenas checkpoint/modelo, prefira o
Network Volume.

### PASSO 3: Criar o endpoint Serverless

1. RunPod Console → Serverless → New Endpoint
2. **Container Image:** `151113/comfyui-ai-film-pipeline:storybook-volume-20260707`
   no endpoint atual, ou `runpod/worker-comfyui:5.8.5-base` apenas se você
   for reconstruir o wrapper/start command manualmente.
3. **GPU:** NVIDIA T4 (mais barata; suficiente para SD1.5)
4. **Network Volume:** anexar o volume criado no passo 2, contendo
   `models/checkpoints/ai-film-comic-storybook-xl.safetensors`.
5. **Workers:** Min 0 (essencial para escalar a zero), Max conforme seu volume
6. **Idle Timeout:** alguns segundos (controla quanto tempo o worker fica de
   pé entre o fim de um job e o desligamento — quanto menor, menos custo
   ocioso, mas mais cold starts se as chamadas forem espaçadas)
7. **Start command:** se o checkpoint está em Network Volume, exponha o volume
   para o diretório padrão do ComfyUI antes de iniciar o handler:

```bash
bash -lc 'set -e; shopt -s nullglob; mkdir -p /comfyui/models/checkpoints; for d in /runpod-volume/models/checkpoints /workspace/models/checkpoints; do if [ -d "$d" ]; then files=("$d"/*); if [ ${#files[@]} -gt 0 ]; then ln -sf "${files[@]}" /comfyui/models/checkpoints/; fi; fi; done; echo AI_FILM_CHECKPOINTS; ls -lh /comfyui/models/checkpoints /runpod-volume/models/checkpoints /workspace/models/checkpoints 2>/dev/null || true; exec /start.sh'
```

Use `/start.sh`, não `python -u /handler.py` direto. O `/start.sh` oficial
faz o pre-flight de GPU, inicia o servidor ComfyUI e depois inicia o handler
RunPod. Se você pular esse bootstrap, o worker pode aparecer como `running`
mas não consumir jobs da fila.

Na imagem customizada deste repositório, esse comportamento fica fixado em
`runpod_worker/start_ai_film.sh`, chamado pelo `CMD` do Dockerfile. Isso evita
depender de override manual no console.

No endpoint `1ivgumnpf8tevg`, o template `vx6kp41lv5` foi atualizado para
usar essa imagem customizada e `dockerArgs=/start_ai_film.sh`.

8. Criar e copiar o **Endpoint ID** exibido no painel

### PASSO 4: Configurar o `.env`

```bash
RUNPOD_API_KEY=sua_api_key
RUNPOD_ENDPOINT_ID=seu_endpoint_id
RUNPOD_NETWORK_VOLUME_ID=o3dykt8fx9
RUNPOD_NETWORK_VOLUME_DATACENTER=EUR-IS-1
IMAGE_GENERATION_PROVIDER=comfyui
COMFYUI_DEFAULT_CHECKPOINT=ai-film-semantic-juggernaut-xl.safetensors
COMFYUI_CHECKPOINT_COMIC_STORYBOOK=ai-film-semantic-juggernaut-xl.safetensors
COMFYUI_CHECKPOINT_CINEMATIC_REALISM=ai-film-cinematic-realism.safetensors
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

Para controlar custo durante testes, use o helper local:

```bash
# Liga capacidade para teste controlado.
python3 scripts/runpod_endpoint_control.py test-capacity --wait 30

# Confere fila e workers.
python3 scripts/runpod_endpoint_control.py health

# Desliga escala e corta worker idle ao final.
python3 scripts/runpod_endpoint_control.py stop --wait 30
```

Depois, rode o pipeline normalmente; `generate_images()` em
`open3d_implementation/core/langgraph_adapter.py` faz o resto.

Smoke test validado em 2026-07-07:

- Job: `78af1a68-af68-462d-81aa-213107dde321-u2`
- Checkpoint: `ai-film-comic-storybook-xl.safetensors`
- Saída: `data/outputs/runpod_checkpoint_smoke.png` (`768x1024`, PNG)
- Estado final: `workersMin=0`, `workersMax=0`, fila zerada, zero workers ativos.

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
