# 🚀 Primeiro Deploy - AI Film Pipeline

## ✅ Status Atual

Você está pronto para fazer o primeiro deploy! Aqui estão as opções:

---

## 🎯 **Opção 1: Deploy com Docker Compose (RECOMENDADO para começar)**

### **Pré-requisitos:**
- ✅ Docker Desktop instalado
- ✅ docker-compose.yml configurado

### **Deploy Rápido:**

```bash
# 1. Iniciar Docker Desktop (já iniciado)
open -a Docker

# 2. Aguardar Docker iniciar (30-60 segundos)
# Verifique se está rodando:
docker ps

# 3. Deploy completo
docker-compose up -d

# 4. Ver status
docker-compose ps

# 5. Ver logs
docker-compose logs -f

# 6. Acessar serviços
# - FastAPI: http://localhost:8080
# - ComfyUI: http://localhost:8188
# - Blender MCP: http://localhost:9877
```

### **Comandos Úteis:**

```bash
# Ver logs de um serviço específico
docker-compose logs -f app
docker-compose logs -f comfyui
docker-compose logs -f blender-mcp

# Reiniciar serviços
docker-compose restart

# Parar tudo
docker-compose down

# Rebuild e restart
docker-compose up -d --build

# Ver uso de recursos
docker stats
```

---

## 🎯 **Opção 2: Deploy com Kubernetes (Para produção)**

### **Pré-requisitos:**
- Minikube ou K3s instalado
- kubectl configurado

### **Setup Minikube:**

```bash
# 1. Instalar minikube (em andamento)
brew install minikube

# 2. Iniciar cluster
minikube start --driver=docker --cpus=4 --memory=8192

# 3. Habilitar addons
minikube addons enable ingress
minikube addons enable metrics-server

# 4. Deploy
cd k8s/
./deploy.sh

# 5. Ver status
kubectl get all -n ai-film

# 6. Port-forward
kubectl port-forward svc/dagster 3000:3000 -n ai-film &
kubectl port-forward svc/flask-upload 5000:5000 -n ai-film &
```

---

## 🎯 **Opção 3: Deploy Local (Sem containers)**

### **Para desenvolvimento rápido:**

```bash
# 1. Configurar variáveis de ambiente
export COMFYUI_URL="https://sua-url.trycloudflare.com"

# 2. Iniciar Dagster
cd open3d_implementation/orchestration
python start_dagster_with_upload.py

# 3. Acessar
# - Dagster UI: http://localhost:3000
# - Upload Interface: http://localhost:5000
```

---

## 📊 **Verificação do Deploy**

### **Docker Compose:**

```bash
# 1. Verificar containers rodando
docker-compose ps

# Esperado:
# langgraph-mcp-app      Up      8080->8080
# langgraph-comfyui      Up      8188->8188
# langgraph-blender-mcp  Up      9877->9877

# 2. Testar endpoints
curl http://localhost:8080/health
curl http://localhost:8188
curl http://localhost:9877/health

# 3. Ver logs
docker-compose logs --tail=50
```

### **Kubernetes:**

```bash
# 1. Verificar pods
kubectl get pods -n ai-film

# Esperado: Todos Running

# 2. Verificar services
kubectl get svc -n ai-film

# 3. Verificar PVCs
kubectl get pvc -n ai-film

# 4. Ver logs
kubectl logs -f deployment/dagster -n ai-film
```

---

## 🐛 **Troubleshooting**

### **Docker não inicia:**

```bash
# Verificar se Docker está rodando
docker ps

# Se não, iniciar manualmente
open -a Docker

# Aguardar 30-60 segundos
```

### **Containers não iniciam:**

```bash
# Ver logs de erro
docker-compose logs

# Rebuild imagens
docker-compose build --no-cache

# Limpar volumes antigos
docker-compose down -v
docker system prune -a
```

### **Portas já em uso:**

```bash
# Verificar o que está usando a porta
lsof -i :8080
lsof -i :8188
lsof -i :9877

# Matar processo se necessário
kill -9 <PID>
```

### **Falta de memória:**

```bash
# Aumentar memória do Docker Desktop
# Docker Desktop > Settings > Resources > Memory: 8GB+

# Ou reduzir serviços
docker-compose up -d app comfyui  # Sem blender
```

---

## 🎬 **Próximos Passos Após Deploy**

### **1. Configurar ComfyUI:**

```bash
# Se usando Colab, atualizar URL
export COMFYUI_URL="https://sua-url.trycloudflare.com"

# Ou usar webhook
python .github/scripts/colab_webhook_handler.py
```

### **2. Testar Pipeline:**

```bash
# Acessar interface de upload
open http://localhost:5000

# Ou usar API diretamente
curl -X POST http://localhost:8080/api/process \
  -H "Content-Type: application/json" \
  -d '{"story": "Uma menina acorda em um quarto iluminado..."}'
```

### **3. Monitorar:**

```bash
# Docker Compose
docker-compose logs -f

# Kubernetes
kubectl logs -f -l app=ai-film -n ai-film --all-containers=true
```

---

## ✅ **Checklist de Deploy**

- [ ] Docker Desktop rodando
- [ ] Containers iniciados (`docker-compose ps`)
- [ ] Todos os serviços healthy
- [ ] Endpoints acessíveis (8080, 8188, 9877)
- [ ] ComfyUI URL configurada
- [ ] Logs sem erros críticos
- [ ] Teste de pipeline executado

---

## 🎉 **Deploy Completo!**

Após seguir os passos acima, você terá:

✅ **FastAPI** rodando na porta 8080
✅ **ComfyUI** rodando na porta 8188
✅ **Blender MCP** rodando na porta 9877
✅ **Volumes persistentes** para dados
✅ **Health checks** configurados
✅ **Logs centralizados**

**Próximo passo:** Teste o pipeline com uma história simples!

```bash
# Exemplo de teste
curl -X POST http://localhost:8080/api/health
```

---

## 📚 **Documentação Adicional**

- **Docker Compose**: `docker-compose.yml`
- **Kubernetes**: `k8s/` + `KUBERNETES_SETUP.md`
- **CI/CD**: `CICD_SETUP.md`
- **Arquitetura**: `K8S_ARCHITECTURE.md`

**Dúvidas?** Consulte a documentação ou execute `make help` no diretório `k8s/`!
