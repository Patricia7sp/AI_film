#!/usr/bin/env python3
"""
🚀 Deploy Automático - Atualiza configurações e dispara CI/CD
Salva mudanças no GitHub e dispara workflow automaticamente
"""
import os
import sys
import subprocess
from pathlib import Path
import json

class AutoDeploy:
    def __init__(self):
        self.root_path = Path(__file__).parent.parent
        self.env_file = self.root_path / 'open3d_implementation' / '.env'
        self.changes = []
        
    def check_git_status(self):
        """Verifica se há mudanças para commitar"""
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=self.root_path,
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    
    def commit_and_push(self, message="chore: update configuration"):
        """Faz commit e push das mudanças"""
        print("\n📝 Commitando mudanças...")
        
        # Add all changes
        subprocess.run(['git', 'add', '.'], cwd=self.root_path, check=True)
        
        # Commit
        subprocess.run(
            ['git', 'commit', '-m', message],
            cwd=self.root_path,
            check=True
        )
        
        # Push
        print("📤 Fazendo push para GitHub...")
        result = subprocess.run(
            ['git', 'push'],
            cwd=self.root_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Push realizado com sucesso!")
            return True
        else:
            print(f"❌ Erro no push: {result.stderr}")
            return False
    
    def trigger_workflow(self, workflow_name="full-auto-colab-pipeline.yml"):
        """Dispara workflow do GitHub Actions"""
        print(f"\n🚀 Disparando workflow: {workflow_name}...")
        
        # Usar gh CLI se disponível
        result = subprocess.run(
            ['gh', 'workflow', 'run', workflow_name],
            cwd=self.root_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✅ Workflow disparado com sucesso!")
            print("\n📊 Acompanhe em:")
            print("   https://github.com/SEU_USUARIO/LANGGRAPH_MCP/actions")
            return True
        else:
            print("⚠️  gh CLI não disponível ou erro ao disparar")
            print("💡 Dispare manualmente em:")
            print("   https://github.com/SEU_USUARIO/LANGGRAPH_MCP/actions")
            return False
    
    def deploy(self, commit_message=None):
        """Executa deploy completo"""
        print("═" * 70)
        print("🚀 AUTO-DEPLOY - CI/CD PIPELINE")
        print("═" * 70)
        
        # 1. Verificar mudanças
        print("\n🔍 Verificando mudanças...")
        changes = self.check_git_status()
        
        if not changes:
            print("⚠️  Nenhuma mudança detectada")
            print("💡 Execute o diagnóstico primeiro:")
            print("   python3 scripts/diagnose_system.py")
            return False
        
        print(f"✅ Mudanças detectadas:\n{changes}\n")
        
        # 2. Commit e push
        message = commit_message or "chore: update configuration for CI/CD"
        if not self.commit_and_push(message):
            return False
        
        # 3. Disparar workflow
        self.trigger_workflow()
        
        print("\n" + "═" * 70)
        print("✅ DEPLOY INICIADO!")
        print("═" * 70)
        print("\n🤖 O que acontecerá agora:")
        print("   1. GitHub Actions detecta push")
        print("   2. Workflow inicia automaticamente")
        print("   3. Colab é disparado (se necessário)")
        print("   4. ComfyUI URL é capturada")
        print("   5. Pipeline completo executa")
        print("   6. Testes de integração rodam")
        print("\n📊 Acompanhe o progresso:")
        print("   https://github.com/SEU_USUARIO/LANGGRAPH_MCP/actions")
        print("\n" + "═" * 70)
        
        return True

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy automático com CI/CD')
    parser.add_argument(
        '--message', '-m',
        type=str,
        help='Mensagem de commit customizada'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Apenas mostra o que seria feito'
    )
    
    args = parser.parse_args()
    
    deployer = AutoDeploy()
    
    if args.dry_run:
        print("🔍 DRY RUN - Apenas verificando mudanças...")
        changes = deployer.check_git_status()
        if changes:
            print(f"\nMudanças que seriam commitadas:\n{changes}")
        else:
            print("\n⚠️  Nenhuma mudança detectada")
    else:
        deployer.deploy(commit_message=args.message)
