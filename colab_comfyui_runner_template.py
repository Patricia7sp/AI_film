# <<<<<<< INÍCIO DO CÓDIGO PARA O NOTEBOOK COLAB >>>>>>>

# CÉLULA 1: Preparar Ambiente e Clonar ComfyUI
# ==============================================
!echo "⏳ Preparando ambiente e instalando dependências..."

# Instalar aria2 para downloads mais rápidos (usado pelo ComfyUI)
!apt-get update -qq
!apt-get install -y -qq aria2

# Clonar o repositório ComfyUI
!git clone https://github.com/comfyanonymous/ComfyUI.git /content/ComfyUI
%cd /content/ComfyUI

!echo "✅ Repositório ComfyUI clonado."

# Instalar dependências do ComfyUI
!echo "⏳ Instalando dependências do ComfyUI..."
!pip install -r requirements.txt --quiet
!pip install xformers --quiet # Opcional, mas pode acelerar se a GPU do Colab suportar bem

!echo "✅ Dependências instaladas."

# CÉLULA 2: Montar Google Drive
# ============================
from google.colab import drive

!echo "⏳ Montando Google Drive... (Siga as instruções para autorizar)"
drive.mount('/content/drive')
!echo "✅ Google Drive montado em /content/drive"

# CÉLULA 3: Criar Links Simbólicos para os Modelos no Google Drive
# ===============================================================
import os

!echo "⏳ Configurando links simbólicos para os modelos..."

# Caminho base para seus modelos sincronizados no Google Drive
# !!! AJUSTE ESTE CAMINHO SE VOCÊ USOU UM NOME DIFERENTE PARA A PASTA NO GDRIVE !!!
GDRIVE_MODELS_PATH = "/content/drive/MyDrive/comfy_models"

# Diretórios de modelos dentro do ComfyUI e seus correspondentes no GDrive
# Adicione ou remova conforme sua estrutura de modelos
model_directories = {
    "checkpoints": "checkpoints",
    "vae": "vae",
    "loras": "loras",
    "controlnet": "controlnet",
    "embeddings": "embeddings",
    "upscale_models": "upscale_models",
    "clip_vision": "clip_vision",
    "gligen": "gligen",
    # Adicione outros diretórios de modelos que você usa, como:
    # "hypernetworks": "hypernetworks",
    # "diffusers": "diffusers",
    # "custom_nodes": "custom_nodes", # Se você sincroniza custom nodes com modelos
}

comfyui_base_models_dir = "/content/ComfyUI/models"

if not os.path.exists(GDRIVE_MODELS_PATH):
    print(f"⚠️ ATENÇÃO: O diretório de modelos no Google Drive ({GDRIVE_MODELS_PATH}) não foi encontrado!")
    print(f"   Verifique se o caminho está correto e se você executou o script 'sync_models_to_gdrive.sh' localmente.")
else:
    print(f"Usando modelos de: {GDRIVE_MODELS_PATH}")
    for comfy_subdir, gdrive_subdir_name in model_directories.items():
        local_model_path = os.path.join(comfyui_base_models_dir, comfy_subdir)
        gdrive_model_path = os.path.join(GDRIVE_MODELS_PATH, gdrive_subdir_name)

        print(f"  Verificando {comfy_subdir}...")
        # Remover diretório local se existir e não for já um link simbólico
        if os.path.exists(local_model_path) and not os.path.islink(local_model_path):
            print(f"    Removendo diretório local existente: {local_model_path}")
            # Use !rm -rf para diretórios, os.rmdir só funciona para vazios
            os.system(f"rm -rf '{local_model_path}'")
        elif os.path.islink(local_model_path):
            print(f"    Link simbólico já existe para {local_model_path}, pulando.")
            continue
        
        # Criar link simbólico se o diretório de origem no GDrive existir
        if os.path.exists(gdrive_model_path):
            try:
                os.symlink(gdrive_model_path, local_model_path)
                print(f"    ✅ Link simbólico criado: '{local_model_path}' -> '{gdrive_model_path}'")
            except Exception as e:
                print(f"    ❌ Erro ao criar link simbólico para {local_model_path}: {e}")
        else:
            print(f"    ⚠️ Diretório de origem no Google Drive não encontrado para {comfy_subdir}: {gdrive_model_path}")
            # Criar o diretório local vazio para que ComfyUI não reclame, se necessário
            if not os.path.exists(local_model_path):
                 os.makedirs(local_model_path)
                 print(f"    Criado diretório local vazio: {local_model_path}")

!echo "✅ Links simbólicos configurados."

# CÉLULA 4: Iniciar ComfyUI e Expor Publicamente
# ==============================================
from google.colab.output import serve_kernel_port_as_window
import threading
import time

!echo "⏳ Iniciando servidor ComfyUI..."

# Mudar para o diretório do ComfyUI
%cd /content/ComfyUI

COMFYUI_PORT = 8188 # Porta padrão do ComfyUI

# Argumentos para o ComfyUI
# --listen: para aceitar conexões de qualquer IP
# --port: definir a porta
# --preview-method auto: para melhor compatibilidade de previews
# --disable-xformers: descomente se xformers causar problemas ou não estiver instalado/compatível
comfyui_args = f"--listen --port {COMFYUI_PORT} --preview-method auto" # --disable-xformers

# Função para rodar o ComfyUI em uma thread separada
def run_comfyui():
    print(f"Iniciando ComfyUI com: python main.py {comfyui_args}")
    os.system(f"python main.py {comfyui_args}")

comfyui_thread = threading.Thread(target=run_comfyui)
comfyui_thread.start()

!echo "⏳ Aguardando ComfyUI iniciar (pode levar alguns instantes)..."
# Dar um tempo para o servidor iniciar antes de tentar expor a porta
time.sleep(15) # Ajuste se necessário

# Expor a porta do ComfyUI para um URL público HTTPS estável
# O URL será mostrado na saída desta célula
serve_kernel_port_as_window(COMFYUI_PORT, path='/', anchor_text='Clique aqui para abrir o ComfyUI Remoto')

!echo "✅ Servidor ComfyUI deve estar rodando e acessível pelo link acima."
!echo "ℹ️  Copie o URL gerado (algo como https://*.colab.google.com/) e use-o com o script 'set_comfy_remote.sh' no seu Mac."
!echo "🔴 O ComfyUI continuará rodando enquanto esta célula estiver em execução e o notebook Colab estiver ativo."

# CÉLULA 5 (Opcional): Manter o Colab Ativo
# ==========================================
# Esta célula pode ajudar a prevenir que o Colab desconecte por inatividade,
# embora o servidor rodando geralmente seja suficiente.
# import time
# print("🕒 Mantendo o Colab ativo...")
# while True:
#   time.sleep(300) # Dorme por 5 minutos
#   print(f"Ativo às {time.ctime()}")

# <<<<<<< FIM DO CÓDIGO PARA O NOTEBOOK COLAB >>>>>>>
