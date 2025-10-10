# Course Transcription MCP - Documentação

## 📚 Visão Geral

O **Course Transcription MCP** é um servidor Model Context Protocol (MCP) desenvolvido para acessar plataformas de cursos online de forma segura e realizar transcrições automáticas de aulas em vídeo.

## 🚀 Características Principais

- **🔐 Segurança**: Armazenamento criptografado de credenciais usando Keyring e Fernet
- **🎥 Transcrição Automática**: Usa OpenAI Whisper para transcrever vídeos
- **🌐 Multi-plataforma**: Suporte para diversas plataformas de cursos
- **🤖 Automação Web**: Usa Playwright para navegação automatizada
- **📝 Extração de Conteúdo**: Captura texto e materiais das páginas

## 📋 Pré-requisitos

- Python 3.8+
- ffmpeg (para processamento de áudio/vídeo)
- 4GB+ RAM (para modelo Whisper)
- Conexão estável com internet

## 🔧 Instalação

### 1. Clone ou baixe os arquivos

```bash
cd /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP
```

### 2. Execute o script de instalação

```bash
chmod +x install_course_mcp.sh
./install_course_mcp.sh
```

O script irá:
- Criar um ambiente virtual Python
- Instalar todas as dependências
- Configurar o Playwright
- Instalar ffmpeg (se necessário)
- Criar estrutura de diretórios
- Gerar arquivos de configuração

### 3. Instalação Manual (opcional)

Se preferir instalar manualmente:

```bash
# Criar ambiente virtual
python3 -m venv .venv_course_mcp
source .venv_course_mcp/bin/activate

# Instalar dependências
pip install -r requirements_course_mcp.txt

# Instalar navegador Playwright
playwright install chromium

# Criar diretórios
mkdir -p logs downloads transcriptions ~/.mcp
```

## 🎯 Uso

### Iniciando o Servidor MCP

```bash
./run_course_mcp.sh
```

### Ferramentas Disponíveis

#### 1. `save_credentials` - Salvar Credenciais

Salva as credenciais de forma segura e criptografada.

**Parâmetros:**
- `platform` (string): Nome da plataforma (ex: "curseduca")
- `username` (string): Email ou nome de usuário
- `password` (string): Senha

**Exemplo:**
```json
{
  "platform": "curseduca",
  "username": "meu_email@example.com",
  "password": "minha_senha_segura"
}
```

#### 2. `transcribe_course` - Transcrever Aula

Faz login na plataforma, baixa o vídeo e transcreve o áudio.

**Parâmetros:**
- `url` (string): URL da aula
- `platform` (string): Nome da plataforma
- `username` (string): Email ou nome de usuário
- `use_saved_credentials` (boolean): Usar credenciais salvas (padrão: true)

**Exemplo:**
```json
{
  "url": "https://curseduca.pro/course/lesson/123",
  "platform": "curseduca",
  "username": "meu_email@example.com",
  "use_saved_credentials": true
}
```

#### 3. `extract_course_content` - Extrair Conteúdo

Extrai conteúdo textual de uma página do curso.

**Parâmetros:**
- `url` (string): URL da página
- `platform` (string): Nome da plataforma
- `username` (string): Email ou nome de usuário

## 🔒 Segurança

### Armazenamento de Credenciais

As credenciais são armazenadas com múltiplas camadas de segurança:

1. **Criptografia Fernet**: Senha criptografada com chave simétrica
2. **Keyring do Sistema**: Integração com gerenciador de senhas do OS
3. **Permissões de Arquivo**: Chave de criptografia com permissão 600
4. **Isolamento**: Credenciais nunca são logadas ou expostas

### Boas Práticas

- ✅ Use senhas específicas para aplicações
- ✅ Ative 2FA quando disponível
- ✅ Revogue acesso quando não usar mais
- ❌ Nunca compartilhe arquivos de chave
- ❌ Não commite credenciais no Git

## 🛠️ Configuração Avançada

### Arquivo de Configuração

Edite `course_mcp_config.json` para personalizar:

```json
{
  "settings": {
    "headless_browser": true,        // Navegador sem interface
    "whisper_model": "medium",       // Modelo: tiny, base, small, medium, large
    "output_directory": "custom/path",
    "temp_directory": "/tmp/custom",
    "log_level": "DEBUG"             // DEBUG, INFO, WARNING, ERROR
  }
}
```

### Adicionar Nova Plataforma

Adicione no `course_mcp_config.json`:

```json
{
  "platforms": {
    "nova_plataforma": {
      "login_url": "https://exemplo.com/login",
      "selectors": {
        "username": "input#email",
        "password": "input#password",
        "submit": "button.login-btn"
      }
    }
  }
}
```

## 📊 Modelos Whisper

| Modelo | Tamanho | RAM Necessária | Velocidade | Qualidade |
|--------|---------|----------------|------------|-----------|
| tiny   | 39 MB   | ~1 GB          | Muito rápida | Básica    |
| base   | 74 MB   | ~1 GB          | Rápida      | Boa       |
| small  | 244 MB  | ~2 GB          | Moderada    | Muito boa |
| medium | 769 MB  | ~5 GB          | Lenta       | Excelente |
| large  | 1550 MB | ~10 GB         | Muito lenta | Superior  |

## 🐛 Solução de Problemas

### Erro: "ffmpeg não encontrado"

**Linux:**
```bash
sudo apt-get update && sudo apt-get install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Baixe de https://ffmpeg.org/download.html

### Erro: "Playwright browser não instalado"

```bash
playwright install chromium
playwright install-deps  # Linux apenas
```

### Erro: "Modelo Whisper não carrega"

- Verifique memória RAM disponível
- Use um modelo menor (tiny ou base)
- Libere memória fechando outros programas

### Erro: "Login falhou"

- Verifique credenciais
- Atualize seletores no config.json
- Use modo não-headless para debug

## 📂 Estrutura de Arquivos

```
LANGGRAPH_MCP/
├── servers/
│   └── course_transcription_mcp.py   # Servidor principal
├── logs/
│   └── course_transcription_mcp.log  # Logs do sistema
├── downloads/                         # Vídeos baixados temporariamente
├── transcriptions/                    # Transcrições salvas
├── course_mcp_config.json            # Configuração
├── requirements_course_mcp.txt       # Dependências Python
├── install_course_mcp.sh            # Script de instalação
├── run_course_mcp.sh                # Script de execução
└── example_usage.py                 # Exemplo de uso
```

## 🔄 Fluxo de Funcionamento

1. **Autenticação**: Login seguro na plataforma
2. **Navegação**: Acessa a URL da aula
3. **Detecção**: Identifica o player de vídeo
4. **Download**: Baixa o vídeo para processamento
5. **Extração**: Separa o áudio do vídeo
6. **Transcrição**: Converte áudio em texto via Whisper
7. **Salvamento**: Gera arquivo com transcrição completa

## 🤝 Contribuindo

Contribuições são bem-vindas! Para contribuir:

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## ⚖️ Considerações Legais

- Use apenas com conteúdo que você tem direito de acessar
- Respeite os termos de serviço das plataformas
- Não redistribua conteúdo protegido por direitos autorais
- Esta ferramenta é para uso educacional e pessoal

## 📞 Suporte

Para problemas ou dúvidas:
- Abra uma issue no GitHub
- Consulte a documentação do MCP
- Verifique os logs em `logs/course_transcription_mcp.log`

## 📄 Licença

Este projeto está sob licença MIT. Veja o arquivo LICENSE para detalhes.

---

**Desenvolvido com ❤️ para facilitar o acesso ao conhecimento**
