# Windsurf MCP Server - Guia de Instalação e Uso

## 🚀 Instalação Rápida

### 1. Teste o servidor
```bash
python3 /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP/test_windsurf_full.py
```

### 2. Atualize a configuração do Claude Desktop

Edite o arquivo `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "meu-projeto": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP"
      ]
    },
    "windsurf": {
      "command": "python3",
      "args": [
        "/usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP/windsurf_mcp_server_full.py"
      ],
      "env": {
        "PYTHONPATH": "/usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP"
      }
    }
  }
}
```

### 3. Reinicie o Claude Desktop

Feche completamente o Claude Desktop e abra novamente.

## 🛠️ Ferramentas Disponíveis

O servidor Windsurf MCP oferece as seguintes ferramentas:

### 1. **execute_command**
Executa comandos shell no diretório do projeto.
```
Exemplo: "Execute o comando ls -la"
```

### 2. **read_file**
Lê o conteúdo de arquivos.
```
Exemplo: "Leia o arquivo README.md"
```

### 3. **write_file**
Cria ou modifica arquivos.
```
Exemplo: "Crie um arquivo test.py com o conteúdo print('Hello')"
```

### 4. **list_files**
Lista arquivos em um diretório.
```
Exemplo: "Liste todos os arquivos Python"
```

### 5. **search_in_files**
Busca texto em arquivos.
```
Exemplo: "Procure por 'TODO' em todos os arquivos Python"
```

### 6. **git_status**
Mostra o status do repositório Git.
```
Exemplo: "Qual o status do Git?"
```

### 7. **create_project_structure**
Cria estrutura completa de projeto.
```
Exemplo: "Crie um projeto FastAPI chamado api-exemplo"
```

## 📊 Monitoramento

### Verificar logs
```bash
tail -f /tmp/windsurf_mcp.log
```

### Testar manualmente
```bash
# Terminal 1 - Iniciar servidor
python3 /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP/windsurf_mcp_server_full.py

# Terminal 2 - Enviar comando de teste
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}' | python3 /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP/windsurf_mcp_server_full.py
```

## 🐛 Resolução de Problemas

### Servidor desconectado
1. Verifique os logs em `/tmp/windsurf_mcp.log`
2. Teste o servidor com o script de teste
3. Verifique se o Python está acessível: `which python3`

### Ferramentas não aparecem
1. Reinicie o Claude Desktop completamente
2. Verifique se o arquivo de configuração está correto
3. Use a versão de debug temporariamente

## 🎯 Exemplos de Uso

### Criar um novo projeto
```
"Crie um projeto FastAPI chamado minha-api"
```

### Explorar código
```
"Liste todos os arquivos Python e procure por funções que começam com 'test_'"
```

### Desenvolvimento
```
"Crie um arquivo utils.py com uma função para validar emails"
```

### Git workflow
```
"Mostre o status do Git e execute git add em todos os arquivos Python modificados"
```

## 🔒 Segurança

- Comandos perigosos são bloqueados (rm -rf, format, etc)
- Arquivos são criados apenas no diretório base
- Timeout de 30 segundos para comandos
- Logs detalhados para auditoria

## 📝 Notas

- O servidor funciona no diretório: `/usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP`
- Todos os caminhos de arquivo são relativos a este diretório
- Use caminhos absolutos quando necessário
- O servidor mantém um log completo em `/tmp/windsurf_mcp.log`

## 🚨 Modo Debug

Se precisar voltar ao modo debug para resolver problemas:

```json
{
  "mcpServers": {
    "windsurf": {
      "command": "python3",
      "args": [
        "/usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP/windsurf_mcp_debug.py"
      ]
    }
  }
}
```

## 💡 Dicas

1. Use comandos naturais em português ou inglês
2. O Claude entenderá o contexto e usará a ferramenta apropriada
3. Você pode combinar múltiplas operações em uma única solicitação
4. O servidor mantém o estado entre comandos na mesma sessão

## 📞 Suporte

- Logs: `/tmp/windsurf_mcp.log`
- Teste: `test_windsurf_full.py`
- Debug: `windsurf_mcp_debug.py`
- Servidor: `windsurf_mcp_server_full.py`
