#!/usr/bin/env python3
"""
Cliente de teste para o Course Transcription MCP
Este cliente permite testar as funcionalidades do servidor MCP
"""

import asyncio
import json
import sys
from typing import Dict, Any, Optional
from pathlib import Path
import getpass

# Adiciona o diretório pai ao path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("Erro: MCP não instalado. Execute: pip install mcp")
    sys.exit(1)

class CourseTranscriptionClient:
    """Cliente para interagir com o Course Transcription MCP Server"""
    
    def __init__(self):
        self.session = None
        self.tools = {}
        
    async def connect(self):
        """Conecta ao servidor MCP"""
        try:
            server_params = StdioServerParameters(
                command="python",
                args=["servers/course_transcription_mcp.py"],
                env=None
            )
            
            transport = await stdio_client(server_params)
            self.session = ClientSession(transport[0], transport[1])
            
            await self.session.initialize()
            
            # Lista ferramentas disponíveis
            response = await self.session.list_tools()
            self.tools = {tool.name: tool for tool in response.tools}
            
            print("✅ Conectado ao Course Transcription MCP Server")
            print(f"📦 Ferramentas disponíveis: {list(self.tools.keys())}")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro ao conectar: {e}")
            return False
    
    async def save_credentials(self, platform: str, username: str, password: str):
        """Salva credenciais de forma segura"""
        if "save_credentials" not in self.tools:
            print("❌ Ferramenta save_credentials não disponível")
            return
        
        try:
            result = await self.session.call_tool(
                "save_credentials",
                {
                    "platform": platform,
                    "username": username,
                    "password": password
                }
            )
            
            print(result.content[0].text if result.content else "Sem resposta")
            
        except Exception as e:
            print(f"❌ Erro ao salvar credenciais: {e}")
    
    async def transcribe_course(self, url: str, platform: str, username: str):
        """Transcreve uma aula"""
        if "transcribe_course" not in self.tools:
            print("❌ Ferramenta transcribe_course não disponível")
            return
        
        try:
            print(f"\n📹 Iniciando transcrição...")
            print(f"   URL: {url}")
            print(f"   Plataforma: {platform}")
            print(f"   Usuário: {username}")
            
            result = await self.session.call_tool(
                "transcribe_course",
                {
                    "url": url,
                    "platform": platform,
                    "username": username,
                    "use_saved_credentials": True
                }
            )
            
            print("\n" + result.content[0].text if result.content else "Sem resposta")
            
        except Exception as e:
            print(f"❌ Erro ao transcrever: {e}")
    
    async def extract_content(self, url: str, platform: str, username: str):
        """Extrai conteúdo de uma página"""
        if "extract_course_content" not in self.tools:
            print("❌ Ferramenta extract_course_content não disponível")
            return
        
        try:
            print(f"\n📄 Extraindo conteúdo...")
            print(f"   URL: {url}")
            
            result = await self.session.call_tool(
                "extract_course_content",
                {
                    "url": url,
                    "platform": platform,
                    "username": username
                }
            )
            
            print("\n" + result.content[0].text if result.content else "Sem resposta")
            
        except Exception as e:
            print(f"❌ Erro ao extrair conteúdo: {e}")
    
    async def disconnect(self):
        """Desconecta do servidor"""
        if self.session:
            await self.session.close()
            print("👋 Desconectado do servidor")

async def interactive_menu():
    """Menu interativo para o cliente"""
    client = CourseTranscriptionClient()
    
    print("╔════════════════════════════════════════════════╗")
    print("║     Course Transcription MCP Client           ║")
    print("╚════════════════════════════════════════════════╝")
    
    # Conecta ao servidor
    if not await client.connect():
        return
    
    while True:
        print("\n┌─────────────────────────────────────┐")
        print("│           MENU PRINCIPAL            │")
        print("├─────────────────────────────────────┤")
        print("│ 1. Salvar credenciais               │")
        print("│ 2. Transcrever aula                 │")
        print("│ 3. Extrair conteúdo da página       │")
        print("│ 4. Configurações                    │")
        print("│ 0. Sair                             │")
        print("└─────────────────────────────────────┘")
        
        choice = input("\nEscolha uma opção: ")
        
        if choice == "1":
            # Salvar credenciais
            print("\n📝 SALVAR CREDENCIAIS")
            print("-" * 40)
            
            platforms = ["curseduca", "udemy", "coursera", "outro"]
            print("Plataformas disponíveis:")
            for i, p in enumerate(platforms, 1):
                print(f"  {i}. {p}")
            
            plat_choice = input("\nEscolha a plataforma (número): ")
            try:
                platform = platforms[int(plat_choice) - 1]
                if platform == "outro":
                    platform = input("Digite o nome da plataforma: ")
            except:
                print("❌ Opção inválida")
                continue
            
            username = input("Email/Username: ")
            password = getpass.getpass("Senha: ")
            
            await client.save_credentials(platform, username, password)
            
        elif choice == "2":
            # Transcrever aula
            print("\n🎬 TRANSCREVER AULA")
            print("-" * 40)
            
            url = input("URL da aula: ")
            platform = input("Plataforma (ex: curseduca): ")
            username = input("Email/Username: ")
            
            await client.transcribe_course(url, platform, username)
            
        elif choice == "3":
            # Extrair conteúdo
            print("\n📄 EXTRAIR CONTEÚDO")
            print("-" * 40)
            
            url = input("URL da página: ")
            platform = input("Plataforma (ex: curseduca): ")
            username = input("Email/Username: ")
            
            await client.extract_content(url, platform, username)
            
        elif choice == "4":
            # Configurações
            print("\n⚙️  CONFIGURAÇÕES")
            print("-" * 40)
            
            config_path = Path("course_mcp_config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                print(json.dumps(config, indent=2))
                
                edit = input("\nDeseja editar as configurações? (s/n): ")
                if edit.lower() == 's':
                    print("Abrindo arquivo de configuração...")
                    import subprocess
                    subprocess.run(["nano", str(config_path)])
            else:
                print("❌ Arquivo de configuração não encontrado")
            
        elif choice == "0":
            # Sair
            break
        
        else:
            print("❌ Opção inválida")
    
    await client.disconnect()

async def quick_transcribe():
    """Modo rápido de transcrição"""
    if len(sys.argv) < 4:
        print("Uso: python client.py <url> <platform> <username>")
        return
    
    url = sys.argv[1]
    platform = sys.argv[2]
    username = sys.argv[3]
    
    client = CourseTranscriptionClient()
    
    if await client.connect():
        await client.transcribe_course(url, platform, username)
        await client.disconnect()

async def main():
    """Função principal"""
    if len(sys.argv) > 1 and sys.argv[1] != "--interactive":
        # Modo rápido
        await quick_transcribe()
    else:
        # Modo interativo
        await interactive_menu()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Programa interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
