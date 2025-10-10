# Makefile para facilitar execução do projeto
PYTHON = python3
PIP = pip3
# Caminho para o script principal do LangGraph
MAIN_SCRIPT=script/run_langgraph_story.py
# Caminho para o painel de monitoramento MCP (usando Streamlit)
MONITOR_SCRIPT=monitoring/monitor_mcp.py
# Caminho para o script de teste MCP
RUN_MCP=run_mcp.py

.PHONY: run_full run_graph monitor clean_logs help

## Roda o sistema completo (LangGraph + Painel MCP)
run_full:
	@echo "[INFO] Iniciando execução do pipeline LangGraph com MCP..."
	@echo "[INFO] Abrindo painel de monitoramento MCP em uma nova janela de terminal..."
	osascript -e 'tell application "Terminal" to do script "streamlit run $(MONITOR_SCRIPT)"'
	@echo "[INFO] Executando o script principal do pipeline..."
	python $(MAIN_SCRIPT)

## Roda apenas o pipeline LangGraph
run_graph:
	@echo "[INFO] Rodando apenas o script principal do pipeline..."
	python $(MAIN_SCRIPT)

## Abre somente o painel de monitoramento (útil para debug/observação)
monitor:
	@echo "[INFO] Abrindo painel de monitoramento MCP..."
	streamlit run $(MONITOR_SCRIPT)

## Roda o script de run_mcp.py
run_mcp:
	@echo "[INFO] Iniciando execução do script de teste MCP..."
	python $(RUN_MCP)

## Limpa os logs salvos no MCP
clean_logs:
	@echo "[INFO] Limpando logs de monitoramento (mcp_logs/)..."
	rm -rf mcp_logs/*

## Mostra ajuda
help:
	@echo "Comandos disponíveis:"
	@echo "  make run_full     - Executa o pipeline + painel MCP"
	@echo "  make run_graph    - Executa somente o pipeline LangGraph"
	@echo "  make monitor      - Abre o painel MCP (Streamlit)"
	@echo "  make clean_logs   - Apaga os logs em mcp_logs/"
	@echo "  make help         - Mostra esta ajuda"