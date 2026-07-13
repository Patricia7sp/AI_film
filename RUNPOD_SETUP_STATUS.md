# RunPod ComfyUI Setup Status

Data da última validação local: 2026-07-09.

## Fonte

Passo a passo oficial do projeto: `RUNPOD_COMFYUI_SETUP.md`.

## Estado Atual

| Passo | Status | Evidência |
|---|---|---|
| 1. Conta RunPod + API Key | Informado pelo Owner como concluído | API Key foi salva localmente pelo Owner em `.env`; não expor valor em chat. |
| 2. Modelo Hugging Face no Network Volume | Concluído | Network Volume `o3dykt8fx9` (`ai-film-comic-models-eur-is-1`, 50GB, `EUR-IS-1`) criado. Checkpoint `ai-film-comic-storybook-xl.safetensors` baixado direto do Hugging Face para `/workspace/models/checkpoints/`, tamanho validado `6,938,350,040` bytes. |
| 3. Endpoint Serverless | Concluído | Endpoint `1ivgumnpf8tevg` atualizado com `networkVolumeId=o3dykt8fx9`, GPUs `BLACKWELL_96,AMPERE_16,AMPERE_24`, `idleTimeout=10s` e template `vx6kp41lv5` apontando para `151113/comfyui-ai-film-pipeline:storybook-volume-20260707`. Para cortar custo fora de teste, manter `workersMin=0`, `workersMax=0`. |
| 4. `.env` | Concluído | `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID=1ivgumnpf8tevg`, `RUNPOD_NETWORK_VOLUME_ID=o3dykt8fx9`, `RUNPOD_NETWORK_VOLUME_DATACENTER=EUR-IS-1` preenchidos em `open3d_implementation/.env`. |
| 5. Teste RunPod | Concluído | Smoke test real concluído em 2026-07-07 com job `78af1a68-af68-462d-81aa-213107dde321-u2`, checkpoint `ai-film-comic-storybook-xl.safetensors`, PNG `data/outputs/runpod_checkpoint_smoke.png` (`768x1024`, `839285` bytes). |
| 6. API Key de gestão Serverless | Parcial | A API comum não libera `adminSlsEndpoint` (`CSR_READ` ausente), mas a mutation pública `saveEndpoint` permite controlar `workersMin/workersMax`. Foi criado `scripts/runpod_endpoint_control.py` para ligar modo teste e desligar custo sem expor segredo. |

## Comandos Criados

```bash
python3 scripts/validate_runpod_setup.py
python3 scripts/validate_runpod_setup.py --test-endpoint
python3 scripts/runpod_endpoint_control.py health
python3 scripts/runpod_endpoint_control.py test-capacity --wait 30
python3 scripts/runpod_endpoint_control.py stop --wait 30
python3 scripts/runpod_endpoint_control.py cancel-job --job-id <RUNPOD_JOB_ID>
scripts/build_runpod_worker.sh SEU_USUARIO/comfyui-ai-film-pipeline:latest
scripts/runpod_download_hf_model.sh semantic-sdxl ai-film-semantic-juggernaut-xl.safetensors
```

## Histórico / Bloqueios Resolvidos

1. Docker Desktop está instalado, mas `open /Applications/Docker.app` falhou com `kLSNoExecutableErr`.
2. O Docker CLI interno funcionou em `/Applications/Docker.app/Contents/Resources/bin/docker` após iniciar o backend manualmente.
3. O primeiro cold start demorou cerca de 6 minutos porque a imagem é grande.
4. A tag antiga `runpod/worker-comfyui:base` não existe no Docker Hub; o Dockerfile usa `runpod/worker-comfyui:5.8.5-base`.
5. A imagem local grande foi removida após push; `/System/Volumes/Data` ficou com aproximadamente `68GiB` livres após limpeza segura.
6. A tentativa de publicar uma imagem com checkpoint embutido falhou por `502 Bad Gateway` no push do layer grande. A solução final usa imagem leve + Network Volume.

## Próxima Ação

Usar o endpoint já atualizado com a imagem publicada:

```text
151113/comfyui-ai-film-pipeline:storybook-volume-20260707
```

Validação integrada de 2026-07-08:

- Infra RunPod: aprovada. Jobs ComfyUI completaram e endpoint voltou para
  `workersMin=0`, `workersMax=0`.
- Áudio: ElevenLabs gerou 3 áudios reais no pipeline.
- Vídeo: caiu para mock porque o gate semântico bloqueou todas as imagens.
- Imagem/modelo: o checkpoint `ai-film-comic-storybook-xl.safetensors`
  funciona tecnicamente, mas falhou em aderência semântica para cena narrativa
  com objeto pequeno. Cena 2 continuou sem Ludovico/açucareiro/ratinho legível
  e chegou a gerar layout em grade. O próximo ajuste real é trocar o checkpoint
  ou adicionar controle/refinamento antes de aceitar cenas.

Decisão operacional de 2026-07-08:

- Trocar o baseline visual `comic_storybook` para
  `ai-film-semantic-juggernaut-xl.safetensors`, baixado de
  `RunDiffusion/Juggernaut-XL-v9` no Hugging Face.
- Motivo: o modelo anterior é estilisticamente próximo de ilustração, mas
  falhou na fidelidade semântica. O novo baseline prioriza obediência a cena,
  personagens, objetos e enquadramento; o visual de quadrinhos deve ser
  recuperado por prompt/refinamento depois.
- Requisito: baixar o arquivo direto no Network Volume em
  `/runpod-volume/models/checkpoints/ai-film-semantic-juggernaut-xl.safetensors`
  antes de apontar a execução real para ele.
- Teste de download via `dockerArgs` no Serverless foi revertido: o worker ficou
  `unhealthy` porque o download bloqueia o bootstrap do handler. O template
  voltou para `dockerArgs=/start_ai_film.sh`.
- Teste de Pod temporário via GraphQL criou o Pod
  `f1tqm59udzkby9` com `python:3.12-slim`, mas o container entrou em restart
  loop sem logs acessíveis pela API GraphQL. O Pod foi terminado e a lista de
  Pods voltou a zero. Próximo caminho operacional: criar um Pod temporário pelo
  Console RunPod com terminal web, anexar o Network Volume `o3dykt8fx9` em
  `EUR-IS-1` e rodar `scripts/runpod_download_hf_model.sh semantic-sdxl
  ai-film-semantic-juggernaut-xl.safetensors`.
- Validação posterior conseguiu deixar
  `ai-film-semantic-juggernaut-xl.safetensors` disponível para o ComfyUI. Job
  `11595a01-71fc-44db-8fb7-76998100bcdc-u2` completou com esse checkpoint e
  gerou `output/scene_2_juggernaut_probe.png`, mas o gate semântico reprovou:
  `semantic_score=42`, `quality_score=64.2`, `semantic_accepted=false`,
  issues principais `adult_alice`, `missing_ludovico`, `style_mismatch` e
  `hero_object_illegible`. Conclusão: Juggernaut valida a infraestrutura e
  melhora a qualidade técnica, mas não atende o alvo de quadrinho/storybook.
- Segundo candidato escolhido: `DreamShaper XL Turbo V2 SFW`, alias
  `animation-sdxl`, arquivo local esperado
  `ai-film-dreamshaper-xl-turbo-sfw.safetensors`. O teste Serverless
  `4769b924-322e-432c-a2db-6bdd28bd6fae-u2` falhou corretamente porque o
  checkpoint ainda não aparece na lista do ComfyUI; checkpoints disponíveis no
  worker eram apenas `ai-film-comic-storybook-xl.safetensors` e
  `ai-film-semantic-juggernaut-xl.safetensors`. Próximo passo: baixar
  DreamShaper pelo terminal web do Pod/console antes de testar novamente.
- Validação posterior em 2026-07-08 manteve um Pod L4 temporário por tempo
  suficiente para baixar o DreamShaper. O job Serverless
  `df03ab64-b8e4-4c14-ae73-15e1c1e50e4d-u1` aceitou o checkpoint
  `ai-film-dreamshaper-xl-turbo-sfw.safetensors`, entrou em `IN_PROGRESS` e
  completou com imagem salva em `output/scene_2_dreamshaper_turbo_probe.png`.
  Isso confirma que o checkpoint está disponível no Network Volume e é lido pelo
  worker ComfyUI. Resultado visual: melhor estética de personagem/storybook que
  Juggernaut, mas ainda reprovado semanticamente para a Cena 2, porque gerou o
  ratinho como protagonista em vez de Alice + Ludovico + ratinho dentro do
  açucareiro. Próximo ajuste real: composição controlada por camadas,
  ControlNet/IPAdapter/inpaint ou geração/refino por personagem/objeto, não
  apenas troca de checkpoint.
- Ajuste de prompt/workflow aplicado depois disso: negativo por cena no workflow
  ComfyUI, preset `turbo` e diretiva de composição `Controlled hero-object
  composition` para impedir ratinho antropomórfico/protagonista. O job
  `ad6ef2f6-8f80-4b07-a82e-6be24033c63d-u1` completou com
  `ai-film-dreamshaper-xl-turbo-sfw.safetensors`, imagem
  `output/scene_2_dreamshaper_turbo_controlled_probe.png`, mas ainda reprovou:
  `semantic_score=35`, `semantic_accepted=false`, issues principais
  `anthropomorphic_mouse`, `missing_ludovico_professor`, `hero_object_missing`
  e `style_mismatch`. Evidência visual: Alice apareceu melhor, mas Ludovico foi
  substituído por um rato humano. Conclusão final desta rodada: txt2img puro
  não é suficiente para esse tipo de cena. Próximo passo técnico deve instalar
  um fluxo controlado real no RunPod: ControlNet pose/depth/lineart,
  IPAdapter/Reference para identidade, ou inpaint em duas fases para inserir o
  ratinho pequeno dentro do açucareiro.
- Teste de decomposição em insert shot isolado também falhou com DreamShaper:
  job `6cb0b3db-670b-4efa-ab44-5fa65a65b01b-u1`, imagem
  `output/scene_2_insert_sugar_mouse_probe.png`, `semantic_score=42`,
  `semantic_accepted=false`. Mesmo sem Alice/Ludovico no prompt, o modelo gerou
  um ratinho antropomórfico vestido em vez de um animal pequeno dentro do
  açucareiro. Conclusão reforçada: para objetos pequenos/animais naturais, o
  próximo passo não deve ser mais prompt engineering nem decomposição de cena em
  txt2img; deve ser inpaint/controlado ou modelo/LoRA específico para animal
  natural.
- Ajuste de status final honesto aplicado em 2026-07-08: o gate visual agora
  marca falhas desse padrão com `control_workflow_required=true`,
  `recommended_generation_strategy=controlled_inpaint` e uma ação operacional
  explícita para não gastar mais retries `txt2img` puros. A UI de curadoria
  exibe esse aviso tanto na cena quanto na comparação de tentativas.
- Preparação sem Docker Desktop para o próximo fluxo controlado: o wrapper
  `/start_ai_film.sh` agora linka também `models/controlnet`, `models/loras`,
  `models/vae`, `models/clip_vision`, `models/ipadapter` e
  `models/upscale_models` do Network Volume para o ComfyUI. O downloader ganhou
  aliases `controlnet-sdxl-canny` e `controlnet-sdxl-depth`, que populam
  `/runpod-volume/models/controlnet/` via Pod temporário.
- O comando recomendado no terminal do Pod temporário agora é único:
  `bash scripts/runpod_prepare_controlnet_volume.sh`. Ele baixa Canny/Depth,
  valida tamanho mínimo e lista `AI_FILM_CONTROLNET_VOLUME_CONTENTS`.
- Se o Pod temporário não tiver o repo clonado, gerar localmente um comando
  autônomo com `python3 scripts/print_runpod_controlnet_install_command.py` e
  colar o resultado no terminal web do Pod.
- Execução real concluída em 2026-07-08: o Pod temporário
  `1vktp1s18ybjvt` (`RTX A4000`, imagem `ubuntu:22.04`) foi criado via
  GraphQL com o Network Volume `o3dykt8fx9` montado em `/runpod-volume`. O
  status HTTP `https://1vktp1s18ybjvt-19123.proxy.runpod.net/status.json`
  retornou `{"status":"ready","detail":"AI_FILM_CONTROLNET_VOLUME_CONTENTS"}`.
  Em seguida o Pod foi terminado e `myself.pods` voltou a `[]`. O endpoint
  Serverless permaneceu com `inQueue=0`, `inProgress=0` e workers `0`.
- Smoke test Serverless ControlNet concluído em 2026-07-08: capacidade ligada
  temporariamente (`workersMax=1`), job
  `e919e511-030f-4651-a490-67f0884d9210-u2` completou usando
  `ControlNetLoader` com `controlnet-canny-sdxl-1.0.safetensors` carregado de
  `/runpod-volume/models/controlnet`. A imagem foi salva em
  `data/outputs/controlnet_smoke.png` (`496182` bytes). Depois do teste, o
  endpoint voltou para `workersMin=0`, `workersMax=0`, `inQueue=0`,
  `inProgress=0` e workers `0`.
- Retry visual controlado integrado em 2026-07-08: a API de retry seletivo
  agora bloqueia escopos visuais (`image`, `image_video`, `full_scene`) com
  HTTP 409 apenas quando a cena exige `control_workflow_required=true` e o
  caminho ControlNet não está operacional. Quando `RUNPOD_API_KEY`,
  `RUNPOD_ENDPOINT_ID` e `COMFYUI_CONTROLNET_CANNY_MODEL` estão disponíveis, o
  retry ComfyUI usa `ControlNetLoader` + `LoadImage` com uma imagem de controle
  derivada da tentativa ativa, enviada via `input.images` do worker oficial
  `runpod/worker-comfyui`.
- Smoke test do retry controlado com referência concluído em 2026-07-08: job
  `00846dd1-0e53-46e1-85b5-3cbc7822432d-u2` completou no endpoint Serverless,
  salvando `data/outputs/controlnet_retry_builder_smoke.png` (`402103` bytes).
  O endpoint foi desligado em seguida e voltou para `workersMin=0`,
  `workersMax=0`, `inQueue=0`, `inProgress=0` e workers `0`. Observação visual:
  o workflow técnico está funcional, mas a imagem ainda não é qualidade final;
  o próximo refinamento deve melhorar o mapa de controle/inpaint ou adicionar
  nó de pré-processamento Canny/Depth real para aumentar legibilidade do hero
  object.
- Refinamento de retry controlado aplicado em 2026-07-09: o fallback de
  ControlNet agora pode enviar uma imagem de controle semântica (`semantic_hero`)
  em vez de derivar só contornos da tentativa ruim. Para a cena do açucareiro,
  o mapa desenha estrutura de mesa, tigela aberta e ratinho branco como objeto
  narrativo principal. A imagem `data/outputs/controlnet_retry_builder_smoke.png`
  passou a mostrar o açucareiro e o ratinho branco, mas ainda ficou borrada.
- Gate técnico anti-blur aplicado em 2026-07-09: `_probe_image_quality` agora
  mede `edge_sharpness`, marca `blurry_image` abaixo de
  `IMAGE_MIN_EDGE_SHARPNESS=24` e `_combine_image_quality` não aceita a cena
  quando houver bloqueio técnico (`technical_quality_below_threshold`), mesmo
  com QA semântico favorável. A imagem de retry existente foi corretamente
  marcada com `edge_sharpness=20.21`, `blurry_image` e `quality_score=76.0`.
- Smoke remoto com preset `high` tentado em 2026-07-09: job
  `d7304020-a69c-4f82-b6b2-66c665fd3865-u1` ficou cerca de 279s em fila
  porque o endpoint estava com `workersMax=0`, depois entrou em execução e
  atingiu timeout local de 420s. O job foi cancelado explicitamente com
  `scripts/runpod_endpoint_control.py cancel-job`, retornando `status=CANCELLED`.
  Estado final verificado: `inQueue=0`, `inProgress=0`, workers `0` e pods
  temporários `[]`.
- Refiner controlado em duas etapas implementado em 2026-07-09: o retry
  seletivo envia a tentativa aprovada com máscara alfa localizada, usa
  `VAEEncodeForInpaint` para reconstruir somente o hero object e executa um
  segundo sampler após upscale latente. O monitor registra máscara, denoise,
  resolução final, checkpoint e parâmetros do refiner.
- Primeiro smoke de inpaint/refiner: job
  `e721503c-4eee-4ddc-ba44-805f1fea39f9-u1` completou em 315s e salvou
  `data/outputs/controlnet_inpaint_refiner_smoke.png` em `1040x1520`. O gate
  reprovou corretamente: `edge_sharpness=14.31`, pois o denoise baixo manteve
  um bloco cinza na área mascarada e o upscale ampliou o borrão.
- Pipeline híbrido calibrado pelos model cards: Juggernaut XL v9 no primeiro
  passe com `DPM++ 2M Karras`, 35 passos e CFG 5; DreamShaper XL Turbo no
  refiner com 6 passos e CFG 2. O job
  `d958dfc7-fe88-4789-8842-65c1219926c8-u2` completou em 555s, salvando
  `data/outputs/controlnet_hybrid_refiner_smoke.png` em `1248x1824`.
  Semanticamente, o ratinho passou a ser natural e legível; o recipiente ainda
  saiu como xícara com alça, não como açucareiro, portanto a imagem não é alvo
  final. A regra de cena agora proíbe explicitamente `teacup`, `cup handle` e
  `saucer` e exige açucareiro com tampa separada.
- O gate de nitidez passou a medir a região narrativa quando há hero object,
  sem confundir desfoque cinematográfico de fundo com falha técnica. No segundo
  smoke: `edge_sharpness` global `17.79`, `focal_edge_sharpness=24.44`, score
  técnico recalculado `87.9`, sem `blurry_image`. O custo aproximado dos dois
  jobs foi USD 0.84 usando `RUNPOD_GPU_USD_PER_SECOND=0.00097`; cobrança real
  pode incluir inicialização/ociosidade conforme o worker alocado.
- Estado final após os dois testes: validação `READY`, endpoint com
  `workersMax=0`, `inQueue=0`, `inProgress=0`, workers `0` e pods temporários
  `[]`.
- Rodada adicional de 2026-07-09 confirmou que prompt negativo não era o
  gargalo isolado. O job `2acad238-a334-4c3a-800d-6e2a29d38529-u1` usou o
  contrato de produção com `teacup`, `cup handle` e `saucer` priorizados, mas
  ainda gerou xícara e terminou em 507s com `focal_edge_sharpness=17.56`.
- O smoke passou a salvar o primeiro inpaint e o resultado do refiner
  separadamente. O job `7718e723-fecf-44a8-8ee0-e4f0f297a184-u2` completou em
  480s. O primeiro passe marcou `focal_edge_sharpness=18.77`; o DreamShaper
  reduziu para `16.15`. As duas imagens também revelaram contornos circulares
  visíveis derivados do Canny. Decisão: DreamShaper não participa mais do retry
  padrão e Canny não é adequado para o mapa semântico desenhado.
- Novo baseline controlado: `semantic_depth` com mapa preenchido de volumes,
  `controlnet-depth-sdxl-1.0.safetensors`, força `0.78`, Juggernaut XL v9 em
  passe único e refiner desabilitado por padrão. O caminho híbrido continua
  disponível apenas quando explicitamente habilitado para diagnóstico.
- O primeiro smoke remoto do baseline Depth, job
  `771b6036-4f9d-4574-ab13-879f7ab2fb22-u2`, não iniciou porque o worker ficou
  `throttled` e o job permaneceu em fila. Ele foi cancelado explicitamente com
  `status=CANCELLED`; nenhuma imagem foi gerada. Estado final confirmado:
  `workersMax=0`, `inQueue=0`, `inProgress=0`, workers `0` e pods `[]`.
- Custo aproximado dos dois jobs concluídos desta rodada: USD 0.96 usando
  `RUNPOD_GPU_USD_PER_SECOND=0.00097`. O job Depth cancelado não teve tempo de
  execução de GPU registrado.

O wrapper agora faz o equivalente ao start command abaixo, mas dentro da
imagem:

```bash
bash -lc 'set -e; shopt -s nullglob; mkdir -p /comfyui/models/checkpoints; for d in /runpod-volume/models/checkpoints /workspace/models/checkpoints; do if [ -d "$d" ]; then files=("$d"/*); if [ ${#files[@]} -gt 0 ]; then ln -sf "${files[@]}" /comfyui/models/checkpoints/; fi; fi; done; echo AI_FILM_CHECKPOINTS; ls -lh /comfyui/models/checkpoints /runpod-volume/models/checkpoints /workspace/models/checkpoints 2>/dev/null || true; exec /start.sh'
```

Não chamar `python -u /handler.py` diretamente. A imagem
oficial `worker-comfyui` usa `/start.sh` para validar GPU, iniciar o ComfyUI
e só então iniciar o handler RunPod. Pular esse bootstrap pode deixar o worker
`running` sem consumir jobs da fila.

Estado operacional final desta rodada: endpoint em `locations=EUR-IS-1`,
`workersMin=0`, `workersMax=0`, fila zerada e zero workers ativos.

Antes de testar geração real, ligar capacidade:

```bash
python3 scripts/runpod_endpoint_control.py test-capacity --wait 30
```

Depois do teste, desligar custo:

```bash
python3 scripts/runpod_endpoint_control.py stop --wait 30
```

Se precisar ler logs/config completa por API, ainda é necessário uma API Key
com escopo real `CSR_READ`; a API comum permitiu gravar texto em `permissions`,
mas isso não concedeu o escopo de CSR.
