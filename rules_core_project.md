# Regras Fundamentais do Projeto LangGraph MCP

## Visão Geral
O LangGraph MCP (Model Context Protocol) é um sistema de pipeline completo para processamento de histórias, geração de animações 3D e composição de vídeos usando processamento de linguagem natural, Blender, e ComfyUI.

## Princípios Arquiteturais

### 1. Pipeline Modular de LangGraph
- O sistema é construído como um grafo de nós usando LangGraph
- Cada nó tem uma responsabilidade única e bem definida
- O estado flui entre os nós, sendo enriquecido em cada etapa
- Sempre manter separação clara entre processamento de texto, geração de recursos, renderização e composição final

### 2. Tratamento Robusto de Erros
- Todo nó DEVE implementar tratamento de erros
- Falhas em um nó não devem interromper o pipeline completo
- Implementar mecanismos de fallback em cada nó
- Registrar erros detalhadamente usando o sistema de logging

### 3. Armazenamento e Organização de Arquivos
- Usar estrutura clara de diretórios (texturas, backgrounds, animações, vídeos)
- Gerar nomes de arquivos únicos usando UUIDs e timestamps
- Verificar a existência de diretórios antes de salvar arquivos
- Criar diretórios automaticamente quando necessário

### 4. Integração com Ferramentas Externas
- Blender para modelagem e renderização 3D
- ComfyUI para geração de imagens com IA
- FFMPEG para processamento e composição de vídeo
- OpenAI API para análise de linguagem natural avançada

### 5. Logging e Monitoramento
- Todo nó DEVE registrar seu progresso usando o objeto `mcp`
- Registrar tanto sucessos quanto falhas
- Incluir informações detalhadas para depuração
- Usar níveis de log apropriados (info, warning, error)

## Estado do LangGraph

O estado (`Open3DAgentState`) contém as seguintes informações essenciais:
- `scenes`: Lista de cenas processadas da história
- `story`: História original
- `session_id`: ID único da sessão
- `status`: Status atual do pipeline
- `textures`: Caminhos para texturas geradas
- `backgrounds`: Caminhos para backgrounds gerados
- `animations`: Caminhos para animações renderizadas
- `final_video`: Caminho para o vídeo final composto
- `output_dirs`: Diretórios para salvar diferentes tipos de arquivos
- `errors`: Lista de erros encontrados durante a execução
- `mcp`: Objeto para logging e comunicação entre nós

## Fluxo de Processamento
1. Processamento da história e extração de cenas
2. Geração de texturas e backgrounds usando ComfyUI
3. Extração de objetos 3D a partir das descrições usando NLP/LLM
4. Criação e renderização de cenas 3D no Blender
5. Renderização de animações para cada cena
6. Composição do vídeo final com transições, áudio e efeitos

## Mecanismos de Fallback
- Texturas/Backgrounds: Gerar imagens placeholder se ComfyUI falhar
- Objetos 3D: Usar objetos padrão se a extração de NLP/LLM falhar
- Animações: Criar vídeo simples se a renderização do Blender falhar
- Vídeo Final: Tentar métodos alternativos de composição, até usar uma única animação se necessário

## Diretrizes de Desenvolvimento
1. Sempre adicionar logging detalhado para todas as operações
2. Implementar validação de entrada e saída em cada nó
3. Garantir que arquivos temporários sejam limpos após o uso
4. Documentar claramente os parâmetros de entrada/saída de cada nó
5. Verificar a existência de arquivos antes e depois de operações críticas
6. Usar métodos assíncronos quando possível para operações demoradas
7. Priorizar robustez sobre desempenho
8. Garantir compatibilidade com ambientes de nuvem (Docker, Cloud Run)

## Considerações de Produção
- Executar em ambiente GPU para renderização eficiente
- Configurar corretamente variáveis de ambiente no arquivo .env
- Usar Docker para isolamento e reprodutibilidade
- Configurar corretamente recursos no Cloud Run Jobs (CPU, RAM, GPU)
- Garantir que todos os serviços (Blender, ComfyUI) estejam configurados para ambiente headless

## Integrações de API e LLM
- Usar a API OpenAI configurada no arquivo .env para análise avançada de texto
- Modelo padrão definido como GPT-4o-mini, mas configurável via variável de ambiente
- Implementar fallbacks robustos para quando a API não estiver disponível
- Utilizar processos NLP locais (Spacy) como segunda opção
- Em último caso, recorrer a métodos baseados em regras simples
