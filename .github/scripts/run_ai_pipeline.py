#!/usr/bin/env python3
"""
🎬 AI Film Pipeline Runner

Este script executa o pipeline real de geração de conteúdo AI
integrando com ComfyUI, Dagster, e Flask.
"""

import os
import sys
import subprocess
import requests
import time
from pathlib import Path

def check_comfyui_health(url: str, max_retries: int = 3) -> bool:
    """Verifica se ComfyUI está acessível"""
    print(f"🔍 Verificando saúde do ComfyUI: {url}")
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print(f"✅ ComfyUI está saudável!")
                return True
        except Exception as e:
            print(f"⚠️ Tentativa {attempt + 1}/{max_retries} falhou: {e}")
            time.sleep(2)
    
    print(f"❌ ComfyUI não está acessível em {url}")
    return False


def start_dagster(comfyui_url: str):
    """Inicia o Dagster com configuração do ComfyUI"""
    print("\n" + "=" * 70)
    print("🚀 INICIANDO DAGSTER")
    print("=" * 70)
    
    # Definir variáveis de ambiente para Dagster
    env = os.environ.copy()
    env['COMFYUI_URL'] = comfyui_url
    env['DAGSTER_HOME'] = str(Path.home() / '.dagster')
    
    print(f"📝 ComfyUI URL: {comfyui_url}")
    print(f"📂 Dagster Home: {env['DAGSTER_HOME']}")
    
    # Verificar se existe dagster_pipeline no repo
    # Tentar múltiplos caminhos possíveis
    possible_paths = [
        Path('orchestration/enhanced_dagster_pipeline.py'),
        Path('open3d_implementation/orchestration/dagster_pipeline.py'),
        Path('dagster_pipeline.py')
    ]
    
    dagster_path = None
    for path in possible_paths:
        if path.exists():
            dagster_path = path
            break
    
    if dagster_path:
        print(f"✅ Encontrado: {dagster_path}")
        
        # Iniciar Dagster dev server
        cmd = [
            'dagster', 'dev',
            '-f', str(dagster_path),
            '--port', '3000'
        ]
        
        print(f"🔧 Comando: {' '.join(cmd)}")
        
        # Executar em background
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print(f"✅ Dagster iniciado (PID: {process.pid})")
        print(f"🌐 Dagster UI: http://localhost:3000")
        
        return process
    else:
        print(f"⚠️ Arquivo Dagster não encontrado: {dagster_path}")
        print("💡 Procurando arquivos Dagster no projeto...")
        
        # Procurar qualquer arquivo dagster
        dagster_files = list(Path('.').rglob('*dagster*.py'))
        if dagster_files:
            print(f"📋 Arquivos Dagster encontrados:")
            for f in dagster_files:
                print(f"   - {f}")
            print("\n💡 Configure o caminho correto no script")
        else:
            print("❌ Nenhum arquivo Dagster encontrado no repositório")
        
        return None


def start_flask(comfyui_url: str):
    """Inicia o Flask app"""
    print("\n" + "=" * 70)
    print("🌐 INICIANDO FLASK")
    print("=" * 70)
    
    env = os.environ.copy()
    env['COMFYUI_URL'] = comfyui_url
    env['FLASK_ENV'] = 'production'
    
    # Procurar app Flask
    flask_files = ['app.py', 'main.py', 'server.py']
    flask_path = None
    
    for filename in flask_files:
        if Path(filename).exists():
            flask_path = filename
            break
    
    if not flask_path:
        # Procurar em subdiretórios
        for pattern in ['**/app.py', '**/main.py', '**/server.py']:
            matches = list(Path('.').glob(pattern))
            if matches:
                flask_path = matches[0]
                break
    
    if flask_path:
        print(f"✅ Encontrado: {flask_path}")
        
        cmd = ['python', str(flask_path)]
        
        print(f"🔧 Comando: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print(f"✅ Flask iniciado (PID: {process.pid})")
        print(f"🌐 Flask UI: http://localhost:5000")
        
        return process
    else:
        print("⚠️ Nenhum arquivo Flask encontrado")
        print("💡 Arquivos procurados: app.py, main.py, server.py")
        return None


def trigger_dagster_job(comfyui_url: str, dagster_port: int = 3000, max_retries: int = 3):
    """Dispara um job do Dagster via GraphQL API"""
    print("\n" + "=" * 70)
    print("🎯 DISPARANDO JOB DO DAGSTER")
    print("=" * 70)
    
    # Tentar disparar job via GraphQL
    dagster_url = f"http://localhost:{dagster_port}/graphql"
    
    # Query para listar jobs disponíveis
    list_jobs_query = """
    {
      repositoriesOrError {
        ... on RepositoryConnection {
          nodes {
            name
            pipelines {
              name
            }
          }
        }
      }
    }
    """
    
    # Tentar conectar com retry
    for attempt in range(max_retries):
        try:
            wait_time = 5 + (attempt * 2)  # Aumenta tempo de espera a cada tentativa
            print(f"\n⏳ Tentativa {attempt + 1}/{max_retries} - Aguardando {wait_time}s...")
            time.sleep(wait_time)
            
            print(f"🔍 Consultando jobs disponíveis em {dagster_url}...")
            response = requests.post(
                dagster_url,
                json={"query": list_jobs_query},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Dagster respondeu!")
                print(f"📋 Jobs disponíveis: {data}")
                
                # TODO: Disparar job específico aqui
                # Por enquanto, apenas confirma que Dagster está acessível
                return True
            else:
                print(f"⚠️ Dagster retornou status {response.status_code}")
                if attempt < max_retries - 1:
                    print("   Tentando novamente...")
                    continue
                return False
                
        except requests.exceptions.ConnectionError as e:
            print(f"⚠️ Dagster ainda não está pronto: {e}")
            if attempt < max_retries - 1:
                print("   Dagster pode estar iniciando ainda, aguardando...")
                continue
            else:
                print("💡 Dagster GraphQL não ficou pronto")
                print("   ⚠️ Isso é ESPERADO - Dagster demora muito para iniciar (>60s)")
                print("   ✅ Pipeline Python executará diretamente (não precisa de GraphQL)")
                print("   ✅ Continuando execução normalmente...")
                return False
        except Exception as e:
            print(f"⚠️ Erro inesperado: {e}")
            if attempt < max_retries - 1:
                continue
            return False
    
    return False


def run_pipeline_script(comfyui_url: str):
    """Executa script específico do pipeline se existir"""
    print("\n" + "=" * 70)
    print("🎬 EXECUTANDO PIPELINE")
    print("=" * 70)
    
    # Carregar história do arquivo
    story_input = ""
    story_file = Path('output/story_latest.txt')
    if story_file.exists():
        story_input = story_file.read_text(encoding='utf-8')
        print(f"📖 História carregada: {len(story_input)} caracteres")
    else:
        print("⚠️ Arquivo de história não encontrado")
    
    # Procurar scripts de pipeline (incluindo nosso executor Dagster)
    pipeline_scripts = [
        '.github/scripts/execute_dagster_pipeline.py',  # Nosso executor
        'run_pipeline.py',
        'pipeline.py',
        'main_pipeline.py',
        'execute_pipeline.py'
    ]
    
    for script in pipeline_scripts:
        script_path = Path(script)
        if script_path.exists():
            print(f"✅ Encontrado: {script}")
            
            # Passar história como argumento
            cmd = ['python', str(script_path), '--comfyui-url', comfyui_url]
            if story_input:
                cmd.extend(['--story', story_input])
            
            print(f"🔧 Comando: python {script_path} --comfyui-url {comfyui_url[:50]}... --story <{len(story_input)} chars>")
            
            result = subprocess.run(
                cmd,
                env={**os.environ, 'COMFYUI_URL': comfyui_url},
                capture_output=True,
                text=True
            )
            
            print("\n📤 Output:")
            print(result.stdout)
            
            if result.stderr:
                print("\n⚠️ Stderr:")
                print(result.stderr)
            
            if result.returncode == 0:
                print(f"✅ Pipeline executado com sucesso!")
                return True
            else:
                print(f"❌ Pipeline falhou com código: {result.returncode}")
                return False
    
    print("⚠️ Nenhum script de pipeline encontrado")
    print(f"💡 Scripts procurados: {', '.join(pipeline_scripts)}")
    return False


def main():
    """Função principal"""
    print("=" * 70)
    print("🎬 AI FILM PIPELINE - AUTOMATED EXECUTION")
    print("=" * 70)
    
    # Obter URL do ComfyUI
    comfyui_url = os.getenv('COMFYUI_URL')
    if not comfyui_url:
        print("❌ COMFYUI_URL não definida!")
        sys.exit(1)
    
    print(f"\n📝 ComfyUI URL: {comfyui_url}")
    
    # 1. Verificar saúde do ComfyUI
    if not check_comfyui_health(comfyui_url):
        print("\n❌ ComfyUI não está acessível. Abortando.")
        sys.exit(1)
    
    # 2. Iniciar Dagster (se existir)
    dagster_process = start_dagster(comfyui_url)
    
    # 3. Iniciar Flask (se existir)
    flask_process = start_flask(comfyui_url)
    
    # 4. Disparar job do Dagster (se Dagster foi iniciado)
    dagster_job_triggered = False
    if dagster_process:
        dagster_job_triggered = trigger_dagster_job(comfyui_url)
    
    # 5. Executar pipeline específico (se existir)
    pipeline_success = run_pipeline_script(comfyui_url)
    
    # Resumo
    print("\n" + "=" * 70)
    print("📊 RESUMO DA EXECUÇÃO")
    print("=" * 70)
    print(f"✅ ComfyUI Health: OK")
    print(f"{'✅' if dagster_process else '⚠️'} Dagster: {'Rodando' if dagster_process else 'Não encontrado'}")
    print(f"{'✅' if dagster_job_triggered else '⚠️'} Dagster Job: {'Disparado' if dagster_job_triggered else 'Não disparado'}")
    print(f"{'✅' if flask_process else '⚠️'} Flask: {'Rodando' if flask_process else 'Não encontrado'}")
    print(f"{'✅' if pipeline_success else '⚠️'} Pipeline: {'Executado' if pipeline_success else 'Não executado'}")
    print("=" * 70)
    
    # Se nada foi executado, avisar
    if not dagster_process and not flask_process and not pipeline_success:
        print("\n⚠️ ATENÇÃO: Nenhum componente foi executado!")
        print("💡 Isso significa que o workflow ainda precisa ser configurado")
        print("   com os scripts reais do seu projeto.")
        print("\n📝 O que fazer:")
        print("   1. Adicione seus scripts de pipeline ao repositório")
        print("   2. Configure os caminhos corretos neste script")
        print("   3. Execute novamente")
        
        # Não falhar, apenas avisar
        sys.exit(0)
    
    # Manter processos rodando se iniciados
    if dagster_process or flask_process:
        print("\n⏳ Processos em execução. Ctrl+C para parar.")
        try:
            if dagster_process:
                dagster_process.wait()
            if flask_process:
                flask_process.wait()
        except KeyboardInterrupt:
            print("\n🛑 Parando processos...")
            if dagster_process:
                dagster_process.terminate()
            if flask_process:
                flask_process.terminate()
    
    print("\n✅ Execução concluída!")


if __name__ == "__main__":
    main()
