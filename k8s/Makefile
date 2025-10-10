.PHONY: help deploy delete status logs port-forward update-comfyui

# Variáveis
NAMESPACE=ai-film
KUBECTL=kubectl

help:
	@echo "🎬 AI Film Pipeline - Kubernetes Management"
	@echo "=========================================="
	@echo ""
	@echo "Comandos disponíveis:"
	@echo "  make deploy          - Deploy completo no Kubernetes"
	@echo "  make delete          - Remove todos os recursos"
	@echo "  make status          - Mostra status de todos os recursos"
	@echo "  make logs            - Mostra logs de todos os pods"
	@echo "  make port-forward    - Configura port-forward para serviços"
	@echo "  make update-comfyui  - Atualiza URL do ComfyUI"
	@echo "  make restart         - Reinicia todos os deployments"
	@echo "  make scale           - Escala deployments"
	@echo ""

deploy:
	@echo "🚀 Deploying AI Film Pipeline..."
	@./deploy.sh

delete:
	@echo "🗑️  Deletando todos os recursos..."
	@$(KUBECTL) delete namespace $(NAMESPACE) --wait=true
	@echo "✅ Recursos deletados"

status:
	@echo "📊 Status dos recursos:"
	@echo "======================="
	@$(KUBECTL) get all -n $(NAMESPACE)
	@echo ""
	@echo "💾 PersistentVolumeClaims:"
	@$(KUBECTL) get pvc -n $(NAMESPACE)
	@echo ""
	@echo "🔐 Secrets e ConfigMaps:"
	@$(KUBECTL) get secrets,configmaps -n $(NAMESPACE)

logs:
	@echo "📝 Logs dos pods:"
	@$(KUBECTL) logs -f -l app=dagster -n $(NAMESPACE) --all-containers=true --tail=100

logs-dagster:
	@$(KUBECTL) logs -f deployment/dagster -n $(NAMESPACE)

logs-langgraph:
	@$(KUBECTL) logs -f deployment/langgraph -n $(NAMESPACE)

logs-comfyui:
	@$(KUBECTL) logs -f statefulset/comfyui -n $(NAMESPACE)

port-forward:
	@echo "🌐 Configurando port-forward..."
	@echo "Dagster UI: http://localhost:3000"
	@echo "Flask Upload: http://localhost:5000"
	@echo "LangGraph API: http://localhost:8080"
	@echo ""
	@$(KUBECTL) port-forward svc/dagster 3000:3000 -n $(NAMESPACE) & \
	$(KUBECTL) port-forward svc/flask-upload 5000:5000 -n $(NAMESPACE) & \
	$(KUBECTL) port-forward svc/langgraph 8080:8080 -n $(NAMESPACE)

update-comfyui:
	@echo "🔄 Atualizando URL do ComfyUI..."
	@read -p "Digite a nova URL do ComfyUI: " url; \
	$(KUBECTL) patch configmap comfyui-config -n $(NAMESPACE) \
		-p "{\"data\":{\"COMFYUI_URL\":\"$$url\",\"COMFYUI_UPDATED_AT\":\"$$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}}"
	@echo "✅ URL atualizada. Reiniciando pods..."
	@$(KUBECTL) rollout restart deployment/dagster -n $(NAMESPACE)
	@$(KUBECTL) rollout restart deployment/langgraph -n $(NAMESPACE)

restart:
	@echo "🔄 Reiniciando deployments..."
	@$(KUBECTL) rollout restart deployment/dagster -n $(NAMESPACE)
	@$(KUBECTL) rollout restart deployment/langgraph -n $(NAMESPACE)
	@$(KUBECTL) rollout restart deployment/flask-upload -n $(NAMESPACE)
	@$(KUBECTL) rollout restart deployment/blender -n $(NAMESPACE)
	@$(KUBECTL) rollout restart deployment/ffmpeg -n $(NAMESPACE)
	@echo "✅ Deployments reiniciados"

scale:
	@echo "📈 Escalando deployments..."
	@read -p "Deployment (dagster/langgraph/flask-upload): " dep; \
	read -p "Número de réplicas: " replicas; \
	$(KUBECTL) scale deployment/$$dep --replicas=$$replicas -n $(NAMESPACE)

watch:
	@watch -n 2 $(KUBECTL) get pods -n $(NAMESPACE)

shell-dagster:
	@$(KUBECTL) exec -it deployment/dagster -n $(NAMESPACE) -- /bin/bash

shell-langgraph:
	@$(KUBECTL) exec -it deployment/langgraph -n $(NAMESPACE) -- /bin/bash

describe-pod:
	@read -p "Nome do pod: " pod; \
	$(KUBECTL) describe pod $$pod -n $(NAMESPACE)

events:
	@$(KUBECTL) get events -n $(NAMESPACE) --sort-by='.lastTimestamp'

top:
	@$(KUBECTL) top pods -n $(NAMESPACE)
	@$(KUBECTL) top nodes
