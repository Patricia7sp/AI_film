#!/usr/bin/env python3
"""
Script para verificar as dependências do sistema necessárias para executar o pipeline.
"""

import os
import sys
import shutil
import subprocess
import platform
from typing import Dict, List, Tuple, Optional

# Cores para saída colorida
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text: str) -> None:
    """Imprime um cabeçalho formatado."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
    print("=" * len(text))

def print_success(text: str) -> None:
    """Imprime uma mensagem de sucesso."""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

def print_warning(text: str) -> None:
    """Imprime um aviso."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

def print_error(text: str) -> None:
    """Imprime uma mensagem de erro."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def check_command(cmd: str, version_flag: str = "--version") -> Tuple[bool, Optional[str]]:
    """Verifica se um comando está disponível e retorna sua versão."""
    try:
        result = subprocess.run(
            [cmd, version_flag],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            version = result.stdout.strip() or result.stderr.strip()
            return True, version.split('\n')[0] if version else "(versão não disponível)"
        return False, None
    except (subprocess.SubprocessError, FileNotFoundError):
        return False, None

def check_docker() -> Tuple[bool, Optional[str], Optional[str]]:
    """Verifica se o Docker está instalado e em execução."""
    docker_installed, docker_version = check_command("docker")
    if not docker_installed:
        return False, None, None
    
    # Verificar se o Docker está em execução
    try:
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        docker_running = True
    except (subprocess.SubprocessError, FileNotFoundError):
        docker_running = False
    
    return docker_running, docker_version, None

def check_docker_compose() -> Tuple[bool, Optional[str]]:
    """Verifica se o Docker Compose está instalado."""
    # Primeiro tenta com docker compose (v2+)
    compose_v2_installed, compose_v2_version = check_command("docker", "compose version")
    if compose_v2_installed:
        return True, compose_v2_version
    
    # Se não encontrar, tenta com docker-compose (v1)
    compose_v1_installed, compose_v1_version = check_command("docker-compose")
    if compose_v1_installed:
        return True, compose_v1_version
    
    return False, None

def check_nvidia_gpu() -> Tuple[bool, Optional[Dict]]:
    """Verifica se há uma GPU NVIDIA disponível."""
    try:
        # Verifica se o comando nvidia-smi está disponível
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            return False, None
        
        # Extrai informações da GPU
        gpu_info = {}
        for line in result.stdout.split('\n'):
            if 'NVIDIA' in line:
                parts = line.split()
                gpu_info['name'] = ' '.join(parts[:-2])
                gpu_info['driver_version'] = parts[-2]
                gpu_info['memory'] = parts[-1]
                break
        
        return True, gpu_info if gpu_info else None
    except (subprocess.SubprocessError, FileNotFoundError):
        return False, None

def check_nvidia_container_toolkit() -> bool:
    """Verifica se o NVIDIA Container Toolkit está instalado."""
    try:
        result = subprocess.run(
            ["docker", "run", "--gpus", "all", "nvidia/cuda:11.8.0-base-ubuntu22.04", "nvidia-smi"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.returncode == 0 and "NVIDIA-SMI" in result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def check_python_version() -> Tuple[bool, str]:
    """Verifica a versão do Python."""
    import platform
    version = platform.python_version()
    major, minor, _ = map(int, version.split('.')[:3])
    
    if major == 3 and minor >= 8:
        return True, version
    return False, version

def check_disk_space(path: str = "/", min_gb: int = 20) -> Tuple[bool, float]:
    """Verifica o espaço em disco disponível."""
    try:
        total, used, free = shutil.disk_usage(path)
        free_gb = free / (2**30)  # Converter para GB
        return free_gb >= min_gb, free_gb
    except Exception:
        return False, 0.0

def check_ram(min_gb: int = 8) -> Tuple[bool, float]:
    """Verifica a memória RAM disponível."""
    try:
        if platform.system() == "Linux":
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
                total_mem = int(meminfo.split('MemTotal:')[1].split('kB')[0].strip()) / (1024**2)  # GB
                available_mem = int(meminfo.split('MemAvailable:')[1].split('kB')[0].strip()) / (1024**2)  # GB
                return available_mem >= min_gb, available_mem
        elif platform.system() == "Darwin":  # macOS
            total_mem = int(subprocess.check_output(['sysctl', '-n', 'hw.memsize']).strip()) / (1024**3)  # GB
            # Estimativa conservadora de memória disponível
            return total_mem >= min_gb, total_mem
        elif platform.system() == "Windows":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            c_ulong = ctypes.c_ulong
            class MEMORYSTATUS(ctypes.Structure):
                _fields_ = [
                    ('dwLength', c_ulong),
                    ('dwMemoryLoad', c_ulong),
                    ('dwTotalPhys', c_ulong),
                    ('dwAvailPhys', c_ulong),
                    ('dwTotalPageFile', c_ulong),
                    ('dwAvailPageFile', c_ulong),
                    ('dwTotalVirtual', c_ulong),
                    ('dwAvailVirtual', c_ulong)
                ]
            memoryStatus = MEMORYSTATUS()
            memoryStatus.dwLength = ctypes.sizeof(MEMORYSTATUS)
            kernel32.GlobalMemoryStatus(ctypes.byref(memoryStatus))
            available_gb = memoryStatus.dwAvailPhys / (1024**3)
            return available_gb >= min_gb, available_gb
        else:
            return False, 0.0
    except Exception:
        return False, 0.0

def main() -> int:
    """Função principal."""
    print_header("Verificação de Dependências do Pipeline de Geração de Vídeos")
    
    all_checks_passed = True
    
    # Verificar Python
    print_header("1. Verificando Python")
    py_ok, py_version = check_python_version()
    if py_ok:
        print_success(f"Python {py_version} (versão compatível)")
    else:
        print_error(f"Python {py_version} (versão incompatível, requer Python 3.8+)")
        all_checks_passed = False
    
    # Verificar Docker
    print_header("2. Verificando Docker")
    docker_running, docker_version, _ = check_docker()
    if docker_running and docker_version:
        print_success(f"Docker em execução: {docker_version}")
    elif docker_version:
        print_error("Docker instalado, mas não está em execução")
        all_checks_passed = False
    else:
        print_error("Docker não encontrado")
        all_checks_passed = False
    
    # Verificar Docker Compose
    compose_installed, compose_version = check_docker_compose()
    if compose_installed and compose_version:
        print_success(f"Docker Compose: {compose_version}")
    else:
        print_error("Docker Compose não encontrado")
        all_checks_passed = False
    
    # Verificar GPU NVIDIA
    print_header("3. Verificando Hardware")
    has_gpu, gpu_info = check_nvidia_gpu()
    if has_gpu and gpu_info:
        print_success(f"GPU NVIDIA detectada: {gpu_info.get('name', 'Desconhecida')}")
        print_success(f"  - Driver: {gpu_info.get('driver_version', 'Desconhecido')}")
        print_success(f"  - Memória: {gpu_info.get('memory', 'Desconhecida')}")
        
        # Verificar NVIDIA Container Toolkit
        if check_nvidia_container_toolkit():
            print_success("NVIDIA Container Toolkit: Instalado e funcionando")
        else:
            print_warning("NVIDIA Container Toolkit não está configurado corretamente")
            all_checks_passed = False
    else:
        print_warning("Nenhuma GPU NVIDIA detectada. A aceleração por GPU não estará disponível.")
        all_checks_passed = False  # Apenas um aviso, não um erro fatal
    
    # Verificar recursos do sistema
    print_header("4. Verificando Recursos do Sistema")
    
    # Espaço em disco
    disk_ok, disk_gb = check_disk_space()
    if disk_ok:
        print_success(f"Espaço em disco disponível: {disk_gb:.1f}GB (mínimo recomendado: 20GB)")
    else:
        print_error(f"Espaço em disco insuficiente: {disk_gb:.1f}GB (mínimo recomendado: 20GB)")
        all_checks_passed = False
    
    # Memória RAM
    ram_ok, ram_gb = check_ram()
    if ram_ok:
        print_success(f"Memória RAM disponível: {ram_gb:.1f}GB (mínimo recomendado: 8GB)")
    else:
        print_error(f"Memória RAM insuficiente: {ram_gb:.1f}GB (mínimo recomendado: 8GB)")
        all_checks_passed = False
    
    # Verificar arquivos necessários
    print_header("5. Verificando Arquivos do Projeto")
    required_files = [
        "docker-compose.yml",
        "Dockerfile.pipeline",
        "Dockerfile.hunyuan3d",
        "run_pipeline.py",
        "comfyui_client.py",
        "hunyuan3d_client.py",
        "requirements.txt"
    ]
    
    missing_files = []
    for file in required_files:
        if os.path.exists(file):
            print_success(f"Arquivo encontrado: {file}")
        else:
            print_error(f"Arquivo não encontrado: {file}")
            missing_files.append(file)
    
    if missing_files:
        all_checks_passed = False
    
    # Resumo
    print_header("Resumo da Verificação")
    if all_checks_passed:
        print_success("✅ Todas as verificações foram aprovadas! Você está pronto para executar o pipeline.")
        print("\nPróximos passos:")
        print("1. Edite o arquivo .env com suas configurações")
        print("2. Execute o comando: ./run.sh -b examples/sample_story.json")
        return 0
    else:
        print_error("❌ Algumas verificações falharam. Por favor, corrija os problemas acima antes de continuar.")
        print("\nSoluções comuns:")
        if not docker_running:
            print("- Inicie o serviço do Docker")
        if not compose_installed:
            print("- Instale o Docker Compose: https://docs.docker.com/compose/install/")
        if not has_gpu:
            print("- Instale os drivers da NVIDIA")
        if missing_files:
            print(f"- Baixe os arquivos ausentes: {', '.join(missing_files)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
