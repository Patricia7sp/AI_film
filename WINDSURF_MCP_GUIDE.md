# 🛠️ Guia Manual de Instalação - Windsurf MCP

## 📋 Pré-requisitos

Antes de começar, certifique-se de ter:

- ✅ **Python 3.8+** instalado
- ✅ **Claude Desktop** instalado
- ✅ **Windsurf IDE** instalado
- ✅ **pip3** disponível

## 🚀 Instalação Automática (Recomendada)

### Opção 1: Execute o script instalador

1. **Torne o script executável e execute:**
```bash
chmod +x windsurf_mcp_installer.sh
./windsurf_mcp_installer.sh
```

### Opção 2: Instalação Manual

Siga este processo se preferir controle total:

## 🔧 Instalação Manual (Passo a Passo)

### Passo 1: Criar Diretório e Ambiente Virtual

```bash
# Criar diretório
mkdir -p ~/.windsurf-mcp
cd ~/.windsurf-mcp

# Criar ambiente virtual
python3 -m venv venv

# Ativar ambiente virtual
# No Linux/macOS:
source venv/bin/activate
# No Windows:
# venv\Scripts\activate

# Instalar dependências
pip install --upgrade pip
pip install mcp websockets httpx
```

### Passo 2: Criar o Servidor MCP

Crie o arquivo `windsurf_mcp_server.py` com o código do servidor (disponível no instalador).

### Passo 3: Configurar Claude Desktop

#### No macOS:
```bash
# Localizar arquivo de configuração
CONFIG_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
```

#### No Linux:
```bash
CONFIG_FILE="$HOME/.config/claude/claude_desktop_config.json"
```

#### No Windows:
```bash
CONFIG_FILE="$APPDATA/Claude/claude_desktop_config.json"
```

### Passo 4: Editar Configuração do Claude

Edite o arquivo de configuração e adicione:

```json
{
  "mcpServers": {
    "windsurf": {
      "command": "/path/to/.windsurf-mcp/venv/bin/python",
      "args": ["/path/to/.windsurf-mcp/windsurf_mcp_server.py"],
      "env": {
        "PYTHONPATH": "/path/to/.windsurf-mcp"
      }
    }
  }
}
```

**Substitua `/path/to/` pelo caminho real para sua pasta home!**

## 🧪 Teste da Instalação

### 1. Teste o Servidor MCP

```bash
cd ~/.windsurf-mcp
source venv/bin/activate  # Linux/macOS
# ou venv\Scripts\activate  # Windows

python windsurf_mcp_server.py
```

Se não houver erros, pressione `Ctrl+C` para parar.

### 2. Teste no Claude Desktop

1. **Feche** completamente o Claude Desktop
2. **Abra** o Claude Desktop novamente
3. **Digite** uma mensagem como:
   ```
   "Liste as ferramentas disponíveis do Windsurf MCP"
   ```

## 🔍 Solução de Problemas

### Problema: "MCP não encontrado"

**Solução:**
```bash
pip install git+https://github.com/modelcontextprotocol/python-sdk.git
```

### Problema: "Windsurf não detectado"

**Solução:**
Encontre manualmente o caminho do Windsurf:

#### macOS:
```bash
find /Applications -name "Windsurf*" 2>/dev/null
```

#### Linux:
```bash
which windsurf
whereis windsurf
```

#### Windows:
```cmd
where windsurf
dir "C:\Program Files\Windsurf" /s
```

### Problema: "Claude não reconhece MCP"

**Verificações:**
1. ✅ Arquivo de configuração no local correto?
2. ✅ Caminhos no JSON estão corretos?
3. ✅ Claude Desktop foi reiniciado?
4. ✅ Permissões de execução no arquivo Python?

### Problema: "Erro de importação Python"

**Solução:**
```bash
cd ~/.windsurf-mcp
source venv/bin/activate
pip install --upgrade mcp websockets httpx asyncio-mqtt
```

## 📁 Estrutura de Arquivos

Após a instalação, você terá:

```
~/.windsurf-mcp/
├── venv/                          # Ambiente virtual Python
├── windsurf_mcp_server.py         # Servidor MCP
└── requirements.txt               # Dependências
```

E o arquivo de configuração em:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%/Claude/claude_desktop_config.json`

## ✅ Verificação Final

Para confirmar que tudo está funcionando:

1. **Abra o Claude Desktop**
2. **Digite:** "Abra meu projeto no Windsurf: /caminho/para/meu/projeto"
3. **Resultado esperado:** Windsurf deve abrir com o projeto

## 🆘 Precisa de Ajuda?

Se encontrar problemas:

1. **Verifique os logs** do Claude Desktop
2. **Execute o teste manual:**
   ```bash
   cd ~/.windsurf-mcp
   python windsurf_mcp_server.py
   ```
3. **Compartilhe a mensagem de erro** para que eu possa ajudar

## 🗑️ Desinstalação

Para remover completamente:

```bash
# Remover arquivos
rm -rf ~/.windsurf-mcp

# Editar configuração do Claude Desktop
# Remover a seção "windsurf" de mcpServers
```