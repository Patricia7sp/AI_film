# Guia de Integração - ComfyUI e Hunyuan3D

Este guia explica como configurar e usar o ComfyUI e o Hunyuan3D no seu projeto de geração de vídeos.

## Pré-requisitos

- Python 3.8 ou superior
- CUDA 11.8 (recomendado para GPU NVIDIA)
- Git
- pip (gerenciador de pacotes Python)

## Instalação

1. **Clone o repositório** (se ainda não tiver feito):
   ```bash
   git clone <seu-repositorio>
   cd langgraph_system/LANGGRAPH_MCP
   ```

2. **Execute o script de instalação**:
   ```bash
   chmod +x setup_ai_models.sh
   ./setup_ai_models.sh
   ```
   
   Siga as instruções na tela. O script irá:
   - Criar um ambiente virtual
   - Instalar todas as dependências
   - Baixar os modelos necessários (opcional)

3. **Baixe os modelos manualmente** (opcional):
   - Para o ComfyUI, baixe os checkpoints e coloque em `ComfyUI/models/checkpoints/`
   - Para o Hunyuan3D, siga as instruções no repositório oficial

## Uso

### Iniciando os serviços

```bash
./start_services.sh
```

Isso iniciará:
- ComfyUI em http://localhost:8188
- Servidor principal em http://localhost:5000

### Usando a API de integração

O módulo `ai_integration.py` fornece uma interface simples para gerar conteúdo:

```python
from script.ai_integration import AIIntegration

# Inicializa a integração
ai = AIIntegration()

# Gera um vídeo a partir de um prompt
result = ai.generate_video(
    prompt="Uma paisagem futurista com cidades flutuantes",
    output_dir="output/generated_video"
)

print(f"Arquivos gerados: {result['images']}")
```

### Fluxo de trabalho personalizado

1. **Personalize os workflows** em `workflows/`
2. **Adicione novos modelos** aos diretórios apropriados
3. **Modifique a lógica de geração** em `script/ai_integration.py`

## Estrutura de diretórios

```
.
├── ComfyUI/               # Instalação do ComfyUI
│   └── models/            # Modelos do ComfyUI
├── Hunyuan3D/             # Instalação do Hunyuan3D
│   └── checkpoints/       # Modelos do Hunyuan3D
├── workflows/             # Fluxos de trabalho personalizados
│   └── text_to_image.json # Exemplo de workflow
├── script/
│   └── ai_integration.py # Integração com as APIs
├── setup_ai_models.sh     # Script de instalação
└── start_services.sh      # Script de inicialização
```

## Solução de problemas

### Problemas comuns

1. **Erros de CUDA**:
   - Verifique se o CUDA está instalado: `nvidia-smi`
   - Atualize os drivers da NVIDIA

2. **Modelos não encontrados**:
   - Verifique se os modelos estão nos diretórios corretos
   - Consulte a documentação de cada ferramenta para os modelos necessários

3. **Problemas de memória**:
   - Reduza o tamanho do batch ou a resolução
   - Use `--medvram` ou `--lowvram` ao iniciar o ComfyUI

## Recursos adicionais

- [Documentação do ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [Documentação do Hunyuan3D](https://github.com/Tencent/Hunyuan3D)
- [Modelos do Stable Diffusion](https://huggingface.co/models?search=stable-diffusion)

## Licença

Consulte os termos de licença de cada ferramenta utilizada.
