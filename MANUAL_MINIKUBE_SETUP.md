# 🚀 Setup Manual do Minikube e KUBE_CONFIG

O minikube está demorando para iniciar. Execute estes comandos **manualmente em um terminal separado**:

---

## 📋 Passo a Passo

### **1. Abrir Terminal Separado**

```bash
# Abra um novo terminal e navegue para o projeto
cd /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP
```

---

### **2. Iniciar Minikube (2-5 minutos)**

```bash
# Iniciar minikube
minikube start --driver=docker

# Aguarde até ver: "Done! kubectl is now configured to use "minikube" cluster"
```

**Saída esperada:**
```
😄  minikube v1.37.0 on Darwin 15.6.1
✨  Using the docker driver based on existing profile
👍  Starting "minikube" primary control-plane node in "minikube" cluster
🚜  Pulling base image v0.0.48 ...
🔥  Creating docker container (CPUs=2, Memory=4000MB) ...
🐳  Preparing Kubernetes v1.32.0 on Docker 27.5.0 ...
🔗  Configuring bridge CNI (Container Networking Interface) ...
🔎  Verifying Kubernetes components...
🌟  Enabled addons: storage-provisioner, default-storageclass
🏄  Done! kubectl is now configured to use "minikube" cluster and "default" namespace by default
```

---

### **3. Verificar Status**

```bash
# Verificar se está rodando
minikube status

# Deve mostrar:
# minikube
# type: Control Plane
# host: Running
# kubelet: Running
# apiserver: Running
# kubeconfig: Configured
```

---

### **4. Testar kubectl**

```bash
# Ver nodes
kubectl get nodes

# Ver cluster info
kubectl cluster-info

# Deve mostrar o cluster rodando
```

---

### **5. Atualizar Secret KUBE_CONFIG**

```bash
# Atualizar secret no GitHub
cat ~/.kube/config | base64 | gh secret set KUBE_CONFIG

# Verificar
gh secret list | grep KUBE_CONFIG
```

---

## ✅ Verificação Final

```bash
# Ver todos os secrets
gh secret list

# Deve mostrar KUBE_CONFIG com timestamp recente
```

---

## 🐛 Troubleshooting

### **Problema: "Docker machine does not exist"**

```bash
# Deletar cluster antigo
minikube delete

# Iniciar novamente
minikube start --driver=docker
```

### **Problema: "Insufficient memory"**

```bash
# Iniciar com menos memória
minikube start --driver=docker --memory=2048
```

### **Problema: "Docker daemon not running"**

```bash
# Abrir Docker Desktop
open -a Docker

# Aguardar Docker iniciar (30-60 segundos)
# Tentar novamente
minikube start --driver=docker
```

---

## 🎯 Comando Único (Copie e Cole)

```bash
# Execute tudo de uma vez (após minikube start)
cd /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP && \
minikube start --driver=docker && \
echo "✅ Minikube iniciado!" && \
kubectl get nodes && \
cat ~/.kube/config | base64 | gh secret set KUBE_CONFIG && \
echo "✅ KUBE_CONFIG atualizado!" && \
gh secret list
```

---

## 📊 Próximos Passos (Após Setup)

```bash
# 1. Deploy no Kubernetes
cd k8s/
./deploy.sh

# 2. Verificar pods
kubectl get all -n ai-film

# 3. Ver logs
kubectl logs -f deployment/dagster -n ai-film
```

---

## 💡 Dica

O minikube pode demorar **2-5 minutos** na primeira vez porque precisa:
1. Baixar a imagem base (~500MB)
2. Criar o container Docker
3. Inicializar o Kubernetes
4. Configurar networking

**Seja paciente e aguarde a mensagem "Done!"** ✅
