# 🚀 Kubernetes Setup - AI Film Pipeline

## 📋 Resumo Executivo

**Resposta à sua pergunta: SIM! Kubernetes é MUITO melhor que Docker Compose para este projeto!**

### **Por quê?**

✅ **9+ Microserviços**: ComfyUI, Blender, Dagster, LangGraph, OpenCV, FFmpeg, Redis, PostgreSQL, Flask
✅ **GPU Scheduling**: Kubernetes aloca GPUs automaticamente para ComfyUI
✅ **Auto-Scaling**: Cada serviço escala independentemente baseado em carga
✅ **Resiliência**: Auto-healing, health checks, zero-downtime deployments
✅ **Storage**: PersistentVolumes para modelos, imagens, vídeos (sobrevivem a restarts)

---

## 🎯 Comparação: Docker Compose vs Kubernetes

| Aspecto | Docker Compose | Kubernetes | Vencedor |
|---------|----------------|------------|----------|
| **Microserviços** | Todos no mesmo host | Distribuído, isolado | ✅ **K8s** |
| **GPU Scheduling** | Manual | Automático | ✅ **K8s** |
| **Auto-Scaling** | ❌ Não | ✅ HPA | ✅ **K8s** |
| **Auto-Healing** | ❌ Manual | ✅ Automático | ✅ **K8s** |
| **Load Balancing** | Nginx externo | Nativo | ✅ **K8s** |
| **Zero-Downtime** | ❌ Não | ✅ Rolling updates | ✅ **K8s** |
| **Storage** | Volumes | PV/PVC | ✅ **K8s** |
| **Service Discovery** | Links | DNS nativo | ✅ **K8s** |
| **Complexidade** | ✅ Simples | Moderada | ⚖️ Empate |
| **Overhead** | ~50MB | ~200MB | ⚖️ Empate |

### **Veredicto: Kubernetes vence 8-0-2!**

---

## 🏗️ Arquitetura Kubernetes

```
┌───────────────────────────────────────────────────────────────┐
│                  KUBERNETES CLUSTER                            │
│                (minikube / k3s / GKE)                          │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────────────────────────────────────────────┐    │
│  │           NAMESPACE: ai-film                          │    │
│  │                                                        │    │
│  │  ┌─────────────────────────────────────────────┐     │    │
│  │  │        APPLICATION LAYER                     │     │    │
│  │  │  • Dagster (2 replicas)                      │     │    │
│  │  │  • LangGraph (3 replicas)                    │     │    │
│  │  │  • Flask Upload (2 replicas)                 │     │    │
│  │  └─────────────────────────────────────────────┘     │    │
│  │                                                        │    │
│  │  ┌─────────────────────────────────────────────┐     │    │
│  │  │        PROCESSING LAYER (GPU)                │     │    │
│  │  │  • ComfyUI (1 replica + GPU)                 │     │    │
│  │  │  • Blender (2 replicas)                      │     │    │
│  │  │  • OpenCV (2 replicas)                       │     │    │
│  │  │  • FFmpeg (2 replicas)                       │     │    │
│  │  └─────────────────────────────────────────────┘     │    │
│  │                                                        │    │
│  │  ┌─────────────────────────────────────────────┐     │    │
│  │  │           DATA LAYER                         │     │    │
│  │  │  • PostgreSQL (1 replica)                    │     │    │
│  │  │  • Redis (1 replica)                         │     │    │
│  │  └─────────────────────────────────────────────┘     │    │
│  │                                                        │    │
│  │  ┌─────────────────────────────────────────────┐     │    │
│  │  │        PERSISTENT STORAGE                    │     │    │
│  │  │  • dagster-pvc (10Gi)                        │     │    │
│  │  │  • images-pvc (50Gi)                         │     │    │
│  │  │  • videos-pvc (100Gi)                        │     │    │
│  │  │  • models-pvc (50Gi)                         │     │    │
│  │  │  • postgres-pvc (10Gi)                       │     │    │
│  │  └─────────────────────────────────────────────┘     │    │
│  └──────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│              EXTERNAL INTEGRATIONS                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │Google Colab  │───▶│  Cloudflare  │───▶│   ComfyUI    │   │
│  │  (GPU T4)    │    │    Tunnel    │    │  in Cluster  │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
└───────────────────────────────────────────────────────────────┘
```

---

## 🚀 Setup Rápido

### **Opção 1: Minikube (Local - Recomendado para Dev)**

```bash
# 1. Instalar minikube
brew install minikube  # macOS
# ou: curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64

# 2. Iniciar cluster
minikube start --driver=docker --cpus=4 --memory=8192 --gpus=all

# 3. Habilitar addons
minikube addons enable ingress
minikube addons enable metrics-server

# 4. Verificar
kubectl cluster-info
```

### **Opção 2: K3s (Lightweight - Produção)**

```bash
# Instalar K3s (muito mais leve!)
curl -sfL https://get.k3s.io | sh -

# Configurar kubectl
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER ~/.kube/config

# Verificar
kubectl get nodes
```

---

## 📦 Deploy Completo

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/langgraph-mcp.git
cd langgraph-mcp

# 2. Criar namespace
kubectl create namespace ai-film

# 3. Criar secrets
kubectl create secret generic comfyui-secret \
  --from-literal=COMFYUI_URL="https://sua-url.trycloudflare.com" \
  -n ai-film

kubectl create secret generic postgres-secret \
  --from-literal=POSTGRES_PASSWORD="sua-senha-segura" \
  -n ai-film

# 4. Deploy storage
kubectl apply -f k8s/storage/

# 5. Deploy data layer
kubectl apply -f k8s/data-layer/

# 6. Deploy processing layer
kubectl apply -f k8s/processing-layer/

# 7. Deploy application layer
kubectl apply -f k8s/app-layer/

# 8. Configurar ingress
kubectl apply -f k8s/ingress.yaml

# 9. Verificar tudo
kubectl get all -n ai-film
```

---

## 🔄 Integração com Google Colab

### **Seu Notebook Colab:**
https://colab.research.google.com/drive/1bfDjw5JGeqExdsUWYM41txvqlCGzOF99

### **Script de Integração Automática:**

```bash
# Executar integração
python .github/scripts/integrate_colab_comfyui.py
```

**O que o script faz:**
1. ✅ Detecta quando Colab está rodando
2. ✅ Obtém URL do túnel Cloudflare automaticamente
3. ✅ Atualiza ConfigMap do Kubernetes
4. ✅ Reinicia pods do ComfyUI para usar nova URL

### **Adicionar ao seu Colab (final do notebook):**

```python
# Notificar GitHub Actions que ComfyUI está pronto
import requests
import json

tunnel_url = "https://sua-url.trycloudflare.com"  # URL do cloudflared

# Salvar em arquivo (para integração local)
with open('/content/comfyui_url.txt', 'w') as f:
    f.write(tunnel_url)

# Ou enviar para webhook (para CI/CD)
webhook_url = "https://seu-webhook.com/comfyui-url"
try:
    requests.post(webhook_url, json={"url": tunnel_url})
    print(f"✅ URL enviada: {tunnel_url}")
except:
    print(f"⚠️ Webhook falhou, mas URL salva em arquivo")
```

---

## 🎯 Vantagens Práticas

### **1. Escalabilidade Independente**

```bash
# ComfyUI: 1 pod com GPU (caro)
kubectl scale deployment comfyui --replicas=1 -n ai-film

# FFmpeg: 10 pods sem GPU (barato)
kubectl scale deployment ffmpeg --replicas=10 -n ai-film

# Auto-scaling baseado em CPU
kubectl autoscale deployment ffmpeg --cpu-percent=70 --min=2 --max=20 -n ai-film
```

### **2. Resiliência Automática**

```yaml
# Health checks garantem que apenas pods saudáveis recebem tráfego
livenessProbe:
  httpGet:
    path: /health
    port: 8188
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8188
  initialDelaySeconds: 5
  periodSeconds: 5
```

### **3. Zero-Downtime Updates**

```bash
# Atualizar imagem sem downtime
kubectl set image deployment/dagster dagster=nova-imagem:v2 -n ai-film

# Rollback se algo der errado
kubectl rollout undo deployment/dagster -n ai-film
```

### **4. Resource Limits**

```yaml
resources:
  requests:
    memory: "2Gi"
    cpu: "1"
    nvidia.com/gpu: "1"  # Para ComfyUI
  limits:
    memory: "4Gi"
    cpu: "2"
    nvidia.com/gpu: "1"
```

---

## 📊 Monitoramento

### **Dashboard Kubernetes**

```bash
# Minikube
minikube dashboard

# K3s/GKE
kubectl proxy
# Acesse: http://localhost:8001/api/v1/namespaces/kubernetes-dashboard/services/https:kubernetes-dashboard:/proxy/
```

### **Logs em Tempo Real**

```bash
# Ver logs de um pod
kubectl logs -f deployment/comfyui -n ai-film

# Ver logs de todos os pods
kubectl logs -f -l app=ai-film -n ai-film --all-containers=true

# Logs do ComfyUI especificamente
kubectl logs -f -l app=comfyui -n ai-film
```

### **Métricas**

```bash
# CPU e memória por pod
kubectl top pods -n ai-film

# CPU e memória por node
kubectl top nodes
```

---

## 🐛 Troubleshooting

### **ComfyUI não inicia**

```bash
# Ver eventos
kubectl describe pod -l app=comfyui -n ai-film

# Ver logs
kubectl logs -f deployment/comfyui -n ai-film

# Verificar GPU
kubectl describe node | grep -A 10 "Allocated resources"
```

### **Storage cheio**

```bash
# Ver uso de PVCs
kubectl get pvc -n ai-film

# Aumentar tamanho (se suportado)
kubectl patch pvc videos-pvc -n ai-film -p '{"spec":{"resources":{"requests":{"storage":"200Gi"}}}}'
```

### **Pods em CrashLoopBackOff**

```bash
# Ver logs do pod que está crashando
kubectl logs deployment/dagster -n ai-film --previous

# Entrar no pod para debug
kubectl exec -it deployment/dagster -n ai-film -- /bin/bash
```

---

## 🎓 Próximos Passos

### **Fase 1: Setup Local** ✅
- [x] Instalar minikube/k3s
- [x] Deploy básico
- [x] Integração com Colab
- [x] Testes locais

### **Fase 2: Produção**
- [ ] Configurar GPU Operator
- [ ] Implementar Prometheus + Grafana
- [ ] Configurar backups automáticos
- [ ] Implementar CI/CD com ArgoCD
- [ ] Configurar Horizontal Pod Autoscaler

### **Fase 3: Otimização**
- [ ] Implementar Istio (service mesh)
- [ ] Configurar distributed tracing
- [ ] Otimizar resource requests/limits
- [ ] Implementar pod disruption budgets

---

## 📚 Recursos Úteis

### **Documentação**
- [Kubernetes Docs](https://kubernetes.io/docs/)
- [Minikube](https://minikube.sigs.k8s.io/docs/)
- [K3s](https://k3s.io/)
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/getting-started.html)

### **Tutoriais**
- [Kubernetes Basics](https://kubernetes.io/docs/tutorials/kubernetes-basics/)
- [GPU Scheduling](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)

---

## ✅ Checklist de Deploy

- [ ] Kubernetes instalado (minikube/k3s/GKE)
- [ ] kubectl configurado
- [ ] Namespace `ai-film` criado
- [ ] Secrets configurados (ComfyUI URL, PostgreSQL password)
- [ ] PersistentVolumes criados
- [ ] Todos os deployments rodando
- [ ] Ingress configurado
- [ ] ComfyUI acessível via Colab
- [ ] Dagster UI acessível (http://ai-film.local:3000)
- [ ] Testes de integração passando

---

## 🎉 Conclusão

**Kubernetes é MUITO superior ao Docker Compose para este projeto porque:**

1. ✅ **9+ microserviços** precisam de orquestração inteligente
2. ✅ **GPU scheduling** automático para ComfyUI
3. ✅ **Escalabilidade** independente por serviço
4. ✅ **Resiliência** com auto-healing e health checks
5. ✅ **Storage persistente** para modelos e outputs
6. ✅ **Zero-downtime** deployments
7. ✅ **Service discovery** nativo
8. ✅ **Monitoramento** integrado

**Overhead:** Apenas ~200MB para control plane (k3s é ainda mais leve!)

**Próximo passo:** Execute o setup e veja a diferença! 🚀
