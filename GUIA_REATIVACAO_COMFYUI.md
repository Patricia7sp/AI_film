# 🚀 Guia de Reativação do ComfyUI

## Status Atual
- ❌ **ComfyUI**: OFFLINE (túnel Cloudflare fechado pelo usuário)
- ✅ **Pipeline Dagster**: Preparado com fallbacks robustos
- ✅ **Sistema de Upload**: Funcionando (Flask + Sensor)
- ✅ **Logging**: Melhorado com instruções claras

## 📋 Quando Reativar o ComfyUI

### 1. Inicie o Túnel no Google Colab
```bash
# No Google Colab, execute:
!nohup python /content/ComfyUI/main.py --listen --port 8188 --preview-method auto > /content/ComfyUI/comfyui.log 2>&1 &
!nohup cloudflared tunnel --url http://localhost:8188 --no-autoupdate > cloudflared.log 2>&1 &

# Aguarde alguns segundos e capture a URL:
!grep -o 'https://[^[:space:]]*\.trycloudflare\.com' cloudflared.log | tail -1
```

### 2. Configure a Nova URL (3 Opções)

#### Opção A: Script Rápido (Recomendado)
```bash
cd /usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP
python open3d_implementation/scripts/setup_comfyui_quick.py "https://nova-url-tunnel.trycloudflare.com"
```

#### Opção B: Variável de Ambiente
```bash
export COMFYUI_URL="https://nova-url-tunnel.trycloudflare.com"
echo "COMFYUI_URL configurada: $COMFYUI_URL"
```

#### Opção C: Modo Interativo
```bash
python open3d_implementation/scripts/setup_comfyui_quick.py --interactive
```

### 3. Reinicie o Pipeline Dagster
```bash
cd open3d_implementation/orchestration
export DAGSTER_HOME=/usr/local/anaconda3/Agentes_youtube/langgraph_system/LANGGRAPH_MCP/open3d_implementation/orchestration
python start_dagster_with_upload.py
```

### 4. Teste o Sistema
```bash
# Teste a conexão ComfyUI
python open3d_implementation/scripts/setup_comfyui_quick.py --test-only

# Acesse as interfaces:
# - Upload: http://localhost:5001
# - Monitoramento: http://localhost:3000
```

## 🔍 Verificação de Status

### Logs do Pipeline
Os logs agora mostram claramente o status do ComfyUI:
- ✅ **Conectado**: "ComfyUI connection successful"
- ❌ **Offline**: "ComfyUI Status: OFFLINE (túnel Cloudflare fechado)"
- 📋 **Fallback**: "Pipeline continuará com geração procedural de fallback"

### Teste de Conectividade
```bash
# Verificar se COMFYUI_URL está definida
echo "COMFYUI_URL: $COMFYUI_URL"

# Testar conexão HTTP
curl -s -o /dev/null -w "%{http_code}" "$COMFYUI_URL/object_info" --connect-timeout 5
```

## 🛠️ Melhorias Implementadas

### 1. Logging Aprimorado
- ✅ Mensagens claras sobre status do ComfyUI
- ✅ Instruções de reativação nos logs
- ✅ Diferenciação entre fallback e erro

### 2. Configuração Dinâmica
- ✅ Script de configuração rápida
- ✅ Suporte a variável de ambiente
- ✅ Arquivo de configuração atualizado
- ✅ Teste de conectividade automático

### 3. Fallbacks Robustos
- ✅ Geração procedural quando ComfyUI offline
- ✅ Pipeline continua executando todos os assets
- ✅ Relatórios indicam uso de fallback

## 📊 Fluxo de Execução Atual

```
Upload de História → Sensor Dagster → Pipeline Execution
                                           ↓
                    ┌─ ComfyUI Online? ─┐
                    ├─ SIM: Geração AI  │
                    └─ NÃO: Fallback    ┘
                                           ↓
                    Composição Final → Relatório
```

## 🎯 Próximos Passos

1. **Quando reativar ComfyUI**: Use o script `setup_comfyui_quick.py`
2. **Teste imediato**: Faça upload de uma história para validar
3. **Monitoramento**: Acompanhe via Dagster UI (localhost:3000)
4. **Logs detalhados**: Verifique os logs para confirmar conexão

## 📞 Suporte

Se houver problemas na reativação:
1. Verifique se o túnel Cloudflare está ativo
2. Confirme que a URL está acessível via navegador
3. Execute o teste de conectividade
4. Verifique os logs do Dagster para diagnóstico detalhado

---
**Status**: Sistema preparado para reativação imediata ✅
