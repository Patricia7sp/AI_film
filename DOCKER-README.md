# LangGraph MCP - Ambiente Docker

Este guia explica como configurar e executar o ambiente Docker para o projeto LangGraph MCP, garantindo que todo o processamento seja feito dentro de contêineres, sem consumir recursos do host.

## 📋 Pré-requisitos

- Docker 20.10+ instalado
- Docker Compose 2.0+
- 16GB de RAM (recomendado)
- 4 vCPUs (recomendado)
- 20GB de espaço em disco livre

## 🚀 Início Rápido

1. **Clone o repositório**
   ```bash
   git clone [URL_DO_REPOSITORIO]
   cd LANGGRAPH_MCP
   ```

2. **Configure as variáveis de ambiente**
   ```bash
   cp .env.docker .env
   # Edite o arquivo .env conforme necessário
   ```

3. **Dê permissão de execução ao script**
   ```bash
   chmod +x run_docker.sh
   ```

4. **Inicie o ambiente Docker**
   ```bash
   ./run_docker.sh
   ```

5. **No menu interativo, selecione a opção 2 (Iniciar contêineres)**

## 🖥️ Acesso aos Serviços

- **Servidor Flask**: http://localhost:5001
- **Interface do ComfyUI**: http://localhost:8188
- **API Hunyuan3D**: http://localhost:8000

## 🛠️ Gerenciamento do Ambiente

### Script de Controle

O script `run_docker.sh` fornece um menu interativo para gerenciar o ambiente:

```
=== 🚀 LangGraph MCP - Gerenciador Docker ===
1. 🔨 Construir imagens
2. 🚀 Iniciar contêineres
3. 🛑 Parar contêineres
4. 🔄 Reconstruir e reiniciar
5. 📜 Ver logs
6. 🐚 Acessar shell do contêiner
7. 📊 Ver uso de recursos
8. 🧹 Limpar recursos não utilizados
9. ℹ️  Mostrar informações do sistema
0. 🚪 Sair
```

### Comandos Manuais

- **Construir imagens**:
  ```bash
  docker-compose build --no-cache
  ```

- **Iniciar contêineres**:
  ```bash
  docker-compose up -d
  ```

- **Parar contêineres**:
  ```bash
  docker-compose down
  ```

- **Acessar logs**:
  ```bash
  docker-compose logs -f
  ```

## 📂 Estrutura de Diretórios

- `/data`: Dados de entrada e cache
- `/models`: Modelos de IA baixados
- `/output`: Resultados e arquivos gerados
- `/logs`: Logs da aplicação
- `/config`: Arquivos de configuração

## 🔒 Segurança

- O Docker é executado em uma rede isolada
- As portas expostas são mapeadas apenas para localhost
- As credenciais são carregadas do arquivo `.env`
- O usuário dentro do contêiner é não-root por padrão

## 🐛 Solução de Problemas

### Contêiner não inicia

1. Verifique os logs:
   ```bash
   docker-compose logs
   ```

2. Verifique se as portas não estão em uso:
   ```bash
   sudo lsof -i :5000,8188,8000
   ```

3. Verifique o uso de recursos:
   ```bash
   docker stats
   ```

### Limpar tudo e recomeçar

```bash
# Parar e remover todos os contêineres
docker-compose down

# Remover volumes
docker volume prune -f

# Remover imagens não utilizadas
docker image prune -f

# Reconstruir e iniciar
docker-compose up -d --build
```

## 📝 Notas de Desenvolvimento

- O ambiente usa volumes nomeados para persistência de dados
- As configurações podem ser ajustadas no arquivo `.env`
- Para desenvolvimento, monte o código-fonte como volume

## 📄 Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.
