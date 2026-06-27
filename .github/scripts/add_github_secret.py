#!/usr/bin/env python3
"""
Script para adicionar secrets no GitHub Repository
Usa a API do GitHub para adicionar secrets de forma segura
"""

import os
import sys
import base64
import requests
from nacl import encoding, public


def get_public_key(repo_owner: str, repo_name: str, github_token: str):
    """
    Obtém a chave pública do repositório para criptografar secrets
    """
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/secrets/public-key"
    
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        return data["key"], data["key_id"]
    else:
        raise Exception(f"Erro ao obter chave pública: {response.status_code} - {response.text}")


def encrypt_secret(public_key: str, secret_value: str) -> str:
    """
    Criptografa o secret usando a chave pública do repositório
    """
    public_key_bytes = base64.b64decode(public_key)
    sealed_box = public.SealedBox(public.PublicKey(public_key_bytes))
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def create_or_update_secret(
    repo_owner: str,
    repo_name: str,
    secret_name: str,
    secret_value: str,
    github_token: str
):
    """
    Cria ou atualiza um secret no repositório
    """
    print(f"🔐 Adicionando secret: {secret_name}")
    
    # 1. Obter chave pública
    print("📥 Obtendo chave pública do repositório...")
    public_key, key_id = get_public_key(repo_owner, repo_name, github_token)
    
    # 2. Criptografar secret
    print("🔒 Criptografando secret...")
    encrypted_value = encrypt_secret(public_key, secret_value)
    
    # 3. Criar/atualizar secret
    print("📤 Enviando secret para GitHub...")
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/secrets/{secret_name}"
    
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    data = {
        "encrypted_value": encrypted_value,
        "key_id": key_id
    }
    
    response = requests.put(url, headers=headers, json=data)
    
    if response.status_code in [201, 204]:
        print(f"✅ Secret '{secret_name}' adicionado com sucesso!")
        return True
    else:
        print(f"❌ Erro ao adicionar secret: {response.status_code}")
        print(f"Resposta: {response.text}")
        return False


def main():
    """
    Função principal
    """
    print("=" * 70)
    print("🔐 ADICIONAR SECRETS NO GITHUB")
    print("=" * 70)
    
    # Configurações
    REPO_OWNER = "Patricia7sp"
    REPO_NAME = "AI_film"
    
    # Obter token do GitHub
    github_token = os.getenv("GITHUB_TOKEN")
    
    if not github_token:
        print("❌ GITHUB_TOKEN não encontrado!")
        print("💡 Defina: export GITHUB_TOKEN='seu_token'")
        print("💡 Ou crie um token em: https://github.com/settings/tokens")
        print("   Permissões necessárias: repo (full control)")
        sys.exit(1)
    
    print(f"📦 Repositório: {REPO_OWNER}/{REPO_NAME}")
    print(f"🔑 Token: {'✅ Configurado' if github_token else '❌ Não encontrado'}")

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY não encontrado!")
        print("💡 Defina: export GEMINI_API_KEY='your-gemini-api-key'")
        sys.exit(1)

    # Secrets para adicionar
    secrets = {
        "GEMINI_API_KEY": gemini_api_key,
        # Adicione outros secrets aqui se necessário
        # "ELEVENLABS_API_KEY": "...",
        # "STABILITY_API_KEY": "...",
    }
    
    print(f"\n📋 Secrets para adicionar: {len(secrets)}")
    for secret_name in secrets.keys():
        print(f"   - {secret_name}")
    
    print("\n" + "=" * 70)
    
    # Adicionar cada secret
    success_count = 0
    for secret_name, secret_value in secrets.items():
        try:
            if create_or_update_secret(
                REPO_OWNER,
                REPO_NAME,
                secret_name,
                secret_value,
                github_token
            ):
                success_count += 1
            print()
        except Exception as e:
            print(f"❌ Erro ao processar {secret_name}: {e}")
            print()
    
    # Resumo
    print("=" * 70)
    print("📊 RESUMO")
    print("=" * 70)
    print(f"✅ Secrets adicionados: {success_count}/{len(secrets)}")
    
    if success_count == len(secrets):
        print("\n🎉 Todos os secrets foram adicionados com sucesso!")
        print("\n🔍 Verifique em:")
        print(f"   https://github.com/{REPO_OWNER}/{REPO_NAME}/settings/secrets/actions")
    else:
        print("\n⚠️ Alguns secrets falharam. Verifique os erros acima.")
    
    print("=" * 70)


if __name__ == "__main__":
    main()
