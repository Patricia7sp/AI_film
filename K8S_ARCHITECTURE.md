# 🎬 Kubernetes Architecture - AI Film Pipeline

## 🎯 Por que Kubernetes?

### **Vantagens para este Projeto:**

✅ **Microserviços Independentes**
- ComfyUI, Blender, Dagster, LangGraph, OpenCV rodando isoladamente
- Escala cada serviço baseado em demanda
- Falha isolada não afeta outros serviços

✅ **Gerenciamento de GPU**
- Kubernetes aloca GPUs automaticamente para ComfyUI
- Suporte nativo a NVIDIA GPU Operator
- Compartilhamento eficiente de recursos GPU

✅ **Auto-Scaling e Auto-Healing**
- HPA (Horizontal Pod Autoscaler) para escalar baseado em CPU/memória
- Reinicialização automática de pods com falha
- Health checks (liveness/readiness probes)

✅ **Storage Persistente**
- PersistentVolumes para modelos, imagens, vídeos
- Dados sobrevivem a restarts
- Compartilhamento entre pods

✅ **Service Discovery**
- DNS interno: `dagster.ai-film.svc.cluster.local`
- Load balancing automático
- Sem IPs hardcoded

---

## 🏗️ Arquitetura Kubernetes

```
┌─────────────────────────────────────────────────────────────────┐
│                    KUBERNETES CLUSTER                            │
│                  (minikube / k3s / GKE)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              INGRESS CONTROLLER                         │    │
│  │          (nginx-ingress / traefik)                      │    │
│  │                                                          │    │
│  │  ai-film.local ──▶ Routes to Services                  │    │
│  └────────────┬─────────────────────────────────────────────┘    │
│               │                                                  │
│  ┌────────────┴─────────────────────────────────────────────┐  │
│  │                    NAMESPACE: ai-film                     │  │
│  │                                                            │  │
│  │  ┌─────────────────────────────────────────────────┐     │  │
│  │  │              APPLICATION LAYER                   │     │  │
│  │  │                                                   │     │  │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │     │  │
│  │  │  │ Dagster  │  │LangGraph │  │  Flask   │      │     │  │
│  │  │  │ Service  │  │  Service │  │ Service  │      │     │  │
│  │  │  │ :3000    │  │  :8080   │  │  :5000   │      │     │  │
│  │  │  └────┬─────┘  └────┬─────┘  └────┬─────┘      │     │  │
│  │  │       │             │             │             │     │  │
│  │  │  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐      │     │  │
│  │  │  │Deployment│  │Deployment│  │Deployment│      │     │  │
│  │  │  │Replicas:2│  │Replicas:3│  │Replicas:2│      │     │  │
│  │  │  └──────────┘  └──────────┘  └──────────┘      │     │  │
│  │  └─────────────────────────────────────────────────┘     │  │
│  │                                                            │  │
│  │  ┌─────────────────────────────────────────────────┐     │  │
│  │  │           PROCESSING LAYER (GPU)                 │     │  │
│  │  │                                                   │     │  │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │     │  │
│  │  │  │ ComfyUI  │  │ Blender  │  │  OpenCV  │      │     │  │
│  │  │  │ Service  │  │ Service  │  │ Service  │      │     │  │
│  │  │  │ :8188    │  │  :9876   │  │  :8000   │      │     │  │
│  │  │  └────┬─────┘  └────┬─────┘  └────┬─────┘      │     │  │
│  │  │       │             │             │             │     │  │
│  │  │  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐      │     │  │
│  │  │  │StatefulS.│  │Deployment│  │Deployment│      │     │  │
│  │  │  │GPU: 1    │  │Replicas:2│  │Replicas:2│      │     │  │
│  │  │  └──────────┘  └──────────┘  └──────────┘      │     │  │
│  │  └─────────────────────────────────────────────────┘     │  │
│  │                                                            │  │
│  │  ┌─────────────────────────────────────────────────┐     │  │
│  │  │              DATA LAYER                          │     │  │
│  │  │                                                   │     │  │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │     │  │
│  │  │  │PostgreSQL│  │  Redis   │  │  FFmpeg  │      │     │  │
│  │  │  │ Service  │  │ Service  │  │ Service  │      │     │  │
│  │  │  │  :5432   │  │  :6379   │  │  :8080   │      │     │  │
│  │  │  └────┬─────┘  └────┬─────┘  └────┬─────┘      │     │  │
│  │  │       │             │             │             │     │  │
│  │  │  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐      │     │  │
│  │  │  │StatefulS.│  │StatefulS.│  │Deployment│      │     │  │
│  │  │  │Replicas:1│  │Replicas:1│  │Replicas:2│      │     │  │
│  │  │  └──────────┘  └──────────┘  └──────────┘      │     │  │
│  │  └─────────────────────────────────────────────────┘     │  │
│  │                                                            │  │
│  │  ┌─────────────────────────────────────────────────┐     │  │
│  │  │         PERSISTENT STORAGE                       │     │  │
│  │  │                                                   │     │  │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │     │  │
│  │  │  │ dagster  │  │  images  │  │  videos  │      │     │  │
│  │  │  │   -pvc   │  │   -pvc   │  │   -pvc   │      │     │  │
│  │  │  │  10Gi    │  │  50Gi    │  │  100Gi   │      │     │  │
│  │  │  └──────────┘  └──────────┘  └──────────┘      │     │  │
│  │  │                                                   │     │  │
│  │  │  ┌──────────┐  ┌──────────┐                     │     │  │
│  │  │  │  models  │  │postgres  │                     │     │  │
│  │  │  │   -pvc   │  │   -pvc   │                     │     │  │
│  │  │  │  50Gi    │  │  10Gi    │                     │     │  │
│  │  │  └──────────┘  └──────────┘                     │     │  │
│  │  └─────────────────────────────────────────────────┘     │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL INTEGRATIONS                         │
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │ Google Colab │────▶│  Cloudflare  │────▶│   ComfyUI    │   │
│  │   (GPU T4)   │     │    Tunnel    │     │  in Cluster  │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Comparação: Docker Compose vs Kubernetes

| Recurso | Docker Compose | Kubernetes | Vencedor |
|---------|----------------|------------|----------|
| **Escalabilidade** | Manual (`docker-compose scale`) | Automática (HPA) | ✅ K8s |
| **Alta Disponibilidade** | ❌ Single host | ✅ Multi-node | ✅ K8s |
| **Auto-healing** | ❌ Manual restart | ✅ Automático | ✅ K8s |
| **Resource Limits** | Básico | Avançado (requests/limits) | ✅ K8s |
| **GPU Scheduling** | Manual | Automático (device plugin) | ✅ K8s |
| **Load Balancing** | Nginx externo | Nativo (Services) | ✅ K8s |
| **Rolling Updates** | ❌ Downtime | ✅ Zero-downtime | ✅ K8s |
| **Service Discovery** | Links/networks | DNS nativo | ✅ K8s |
| **Secrets Management** | .env files | Secrets API | ✅ K8s |
| **Storage** | Volumes | PV/PVC (dinâmico) | ✅ K8s |
| **Monitoring** | Logs manuais | Prometheus/Grafana | ✅ K8s |
| **Complexidade** | ✅ Simples | Moderada | ⚖️ Empate |
| **Curva de Aprendizado** | ✅ Baixa | Alta | ⚖️ Empate |
| **Overhead** | ~50MB | ~200MB (control plane) | ⚖️ Empate |

### **Veredicto: Kubernetes é MUITO melhor para este projeto!**

**Motivos:**
1. ✅ **9+ microserviços** (ComfyUI, Blender, Dagster, LangGraph, OpenCV, FFmpeg, Redis, PostgreSQL, Flask)
2. ✅ **Necessidade de GPU** (ComfyUI precisa de scheduling inteligente)
3. ✅ **Escalabilidade** (FFmpeg pode precisar de 10 réplicas, ComfyUI apenas 1)
4. ✅ **Resiliência** (Se Blender cai, não pode derrubar o pipeline inteiro)
5. ✅ **Storage** (Modelos, imagens, vídeos precisam persistir)

---

## 🚀 Setup Kubernetes

### **Opção 1: Minikube (Local - Recomendado para Dev)**

```bash
# Instalar minikube
brew install minikube  # macOS
# ou: curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64

# Iniciar com GPU (se disponível)
minikube start --driver=docker --cpus=4 --memory=8192 --gpus=all

# Habilitar addons
minikube addons enable ingress
minikube addons enable metrics-server
minikube addons enable dashboard

# Verificar
kubectl cluster-info
```

### **Opção 2: K3s (Lightweight - Produção)**

```bash
# Instalar K3s (muito mais leve que K8s completo)
curl -sfL https://get.k3s.io | sh -

# Verificar
sudo k3s kubectl get nodes
```

### **Opção 3: GKE (Cloud - Quando escalar)**

```bash
# Criar cluster GKE com GPUs
gcloud container clusters create ai-film-cluster \
  --zone=us-central1-a \
  --machine-type=n1-standard-4 \
  --num-nodes=3 \
  --accelerator type=nvidia-tesla-t4,count=1 \
  --enable-autoscaling --min-nodes=1 --max-nodes=10
```

---

## 📦 Deploy no Kubernetes

```bash
# 1. Criar namespace
kubectl apply -f k8s/namespace.yaml

# 2. Criar secrets
kubectl apply -f k8s/secrets/

# 3. Criar PersistentVolumes
kubectl apply -f k8s/storage/

# 4. Deploy serviços de dados
kubectl apply -f k8s/data-layer/

# 5. Deploy serviços de processamento
kubectl apply -f k8s/processing-layer/

# 6. Deploy aplicação
kubectl apply -f k8s/app-layer/

# 7. Configurar ingress
kubectl apply -f k8s/ingress.yaml

# 8. Verificar
kubectl get all -n ai-film
```

---

## 🔄 Integração com Google Colab

### **Fluxo Automatizado:**

```
┌─────────────┐
│   GitHub    │
│   Actions   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Trigger   │
│Colab Webhook│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Google Colab │
│Start ComfyUI│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Cloudflare  │
│   Tunnel    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Update K8s │
│  ConfigMap  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Restart    │
│ComfyUI Pods │
└─────────────┘
```

### **Script de Integração:**

Vou criar o script que se integra com seu Colab automaticamente!

---

## 🎯 Benefícios Finais

### **Com Kubernetes você ganha:**

1. ✅ **Escalabilidade Automática**
   - ComfyUI: 1 pod com GPU
   - FFmpeg: 5 pods sem GPU (escala baseado em carga)
   - Dagster: 2 pods (alta disponibilidade)

2. ✅ **Resiliência**
   - Se ComfyUI cai, K8s reinicia em segundos
   - Health checks garantem tráfego apenas para pods saudáveis
   - Rolling updates sem downtime

3. ✅ **Gerenciamento de Recursos**
   - GPU alocada automaticamente para ComfyUI
   - Limites de CPU/memória por serviço
   - Evita que um serviço consuma tudo

4. ✅ **Storage Persistente**
   - Modelos Stable Diffusion: 50GB PVC
   - Imagens geradas: 50GB PVC
   - Vídeos: 100GB PVC
   - Dados sobrevivem a restarts

5. ✅ **Monitoramento**
   - Prometheus + Grafana integrados
   - Métricas de CPU, memória, GPU por pod
   - Alertas automáticos

---

## 📚 Próximos Passos

1. ✅ Criar manifestos Kubernetes completos
2. ✅ Script de integração com Colab
3. ✅ Configurar CI/CD para deploy K8s
4. ✅ Helm charts para facilitar deploy
5. ✅ Monitoramento com Prometheus

**Vou criar tudo isso agora!** 🚀
