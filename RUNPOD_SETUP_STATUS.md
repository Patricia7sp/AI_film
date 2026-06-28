# RunPod ComfyUI Setup Status

Data da última validação local: 2026-06-27.

## Fonte

Passo a passo oficial do projeto: `RUNPOD_COMFYUI_SETUP.md`.

## Estado Atual

| Passo | Status | Evidência |
|---|---|---|
| 1. Conta RunPod + API Key | Informado pelo Owner como concluído | API Key foi salva localmente pelo Owner em `.env`; não expor valor em chat. |
| 2. Build da imagem customizada | Concluído | Imagem local `151113/comfyui-ai-film-pipeline:latest`, image id `493965dd7d97`, tamanho `40.3GB`. Push concluído com digest `sha256:493965dd7d974261423e21f5f2b74522a32341bf33b33ad7263f10bead7de3c0`. |
| 3. Endpoint Serverless | Concluído | Endpoint `ai-film-comfyui-sd15` criado no RunPod com ID `1ivgumnpf8tevg`. Configuração validada: Queue, GPU 16GB/RTX A4500 class, `workersMin=0`, `workersMax=1`, `idleTimeout=5s`, `containerDiskInGb=60`. |
| 4. `.env` | Concluído | `RUNPOD_API_KEY` presente e `RUNPOD_ENDPOINT_ID=1ivgumnpf8tevg` preenchido em `open3d_implementation/.env`. |
| 5. Teste RunPod | Concluído para conectividade | Request de teste com workflow vazio alcançou o worker e retornou erro esperado `Prompt has no outputs`, confirmando autenticação e endpoint. |

## Comandos Criados

```bash
python3 scripts/validate_runpod_setup.py
python3 scripts/validate_runpod_setup.py --test-endpoint
scripts/build_runpod_worker.sh SEU_USUARIO/comfyui-ai-film-pipeline:latest
```

## Bloqueios Reais Nesta Máquina

1. Docker Desktop está instalado, mas `open /Applications/Docker.app` falhou com `kLSNoExecutableErr`.
2. O Docker CLI interno funcionou em `/Applications/Docker.app/Contents/Resources/bin/docker` após iniciar o backend manualmente.
3. O primeiro cold start demorou cerca de 6 minutos porque a imagem é grande.
4. A tag antiga `runpod/worker-comfyui:base` não existe no Docker Hub; o Dockerfile foi atualizado para `runpod/worker-comfyui:5.8.6-base`.
5. A imagem local grande foi removida após push; `/System/Volumes/Data` ficou com aproximadamente `68GiB` livres após limpeza segura.

## Próxima Ação

Executar um teste com workflow ComfyUI real do projeto, porque o teste vazio só valida conectividade e autenticação.
