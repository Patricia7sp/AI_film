#!/usr/bin/env python3
"""
Playwright Colab Trigger
Inicia Google Colab automaticamente usando Playwright
Mais moderno e confiável que Selenium
"""

import os
import sys
import time
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


class PlaywrightColabTrigger:
    """
    Trigger automático do Google Colab usando Playwright
    """
    
    def __init__(self):
        self.google_email = os.getenv('GOOGLE_EMAIL')
        self.google_password = os.getenv('GOOGLE_PASSWORD')
        self.notebook_id = os.getenv('COLAB_NOTEBOOK_ID')
        self.headless = os.getenv('HEADLESS', 'true').lower() == 'true'
        self.timeout = 60000  # 60 segundos
    
    def log(self, message: str, level: str = "INFO"):
        """Log estruturado"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] [{level}] {message}")
    
    async def trigger_colab(self) -> bool:
        """
        Método principal: Inicia Colab automaticamente
        """
        self.log("🎭 Iniciando Playwright Colab Trigger...")
        
        # Validar configuração
        if not self._validate_config():
            return False
        
        async with async_playwright() as p:
            try:
                # Iniciar navegador
                browser = await self._launch_browser(p)
                
                # Criar contexto com cookies persistentes
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                page = await context.new_page()
                
                # Passo 1: Login no Google
                if not await self._login_google(page):
                    await browser.close()
                    return False
                
                # Passo 2: Abrir Colab Notebook
                if not await self._open_notebook(page):
                    await browser.close()
                    return False
                
                # Passo 3: Conectar ao Runtime
                if not await self._connect_runtime(page):
                    await browser.close()
                    return False
                
                # Passo 4: Executar todas as células
                if not await self._execute_all_cells(page):
                    await browser.close()
                    return False
                
                # Passo 5: Aguardar execução iniciar
                await self._wait_for_execution(page)
                
                self.log("=" * 60)
                self.log("✅ Colab iniciado com sucesso!")
                self.log("📡 Notebook está executando automaticamente")
                self.log("⏳ Aguarde o auto-reporter enviar a URL para o Gist")
                
                # Manter navegador aberto por 30 segundos para garantir execução
                self.log("⏳ Mantendo sessão ativa por 30 segundos...")
                await asyncio.sleep(30)
                
                await browser.close()
                return True
                
            except Exception as e:
                self.log(f"❌ Erro durante execução: {e}", "ERROR")
                return False
    
    def _validate_config(self) -> bool:
        """Valida configuração necessária"""
        if not self.google_email:
            self.log("❌ GOOGLE_EMAIL não configurado", "ERROR")
            return False
        
        if not self.google_password:
            self.log("❌ GOOGLE_PASSWORD não configurado", "ERROR")
            return False
        
        if not self.notebook_id:
            self.log("❌ COLAB_NOTEBOOK_ID não configurado", "ERROR")
            return False
        
        self.log("✅ Configuração validada")
        return True
    
    async def _launch_browser(self, playwright):
        """Inicia navegador Chromium"""
        self.log("🌐 Iniciando navegador Chromium...")
        
        browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        
        self.log("✅ Navegador iniciado")
        return browser
    
    async def _login_google(self, page) -> bool:
        """
        Faz login no Google
        """
        try:
            self.log("🔐 Fazendo login no Google...")
            
            # Ir para página de login
            await page.goto('https://accounts.google.com/signin', wait_until='networkidle')
            
            # Passo 1: Email
            self.log("📧 Inserindo email...")
            await page.fill('input[type="email"]', self.google_email)
            await page.click('button:has-text("Next"), button:has-text("Próxima")')
            await page.wait_for_timeout(2000)
            
            # Passo 2: Senha
            self.log("🔑 Inserindo senha...")
            await page.fill('input[type="password"]', self.google_password)
            await page.click('button:has-text("Next"), button:has-text("Próxima")')
            
            # Aguardar login completar
            await page.wait_for_url('https://myaccount.google.com/**', timeout=30000)
            
            self.log("✅ Login realizado com sucesso!")
            return True
            
        except PlaywrightTimeout:
            self.log("⚠️ Timeout no login - pode ter 2FA ativado", "WARN")
            self.log("💡 Considere usar Service Account ao invés de login manual")
            return False
        except Exception as e:
            self.log(f"❌ Erro no login: {e}", "ERROR")
            return False
    
    async def _open_notebook(self, page) -> bool:
        """
        Abre notebook no Colab
        """
        try:
            self.log("📓 Abrindo notebook no Colab...")
            
            notebook_url = f"https://colab.research.google.com/drive/{self.notebook_id}"
            await page.goto(notebook_url, wait_until='networkidle')
            
            # Aguardar notebook carregar
            await page.wait_for_selector('.notebook-container, #notebook', timeout=30000)
            
            self.log("✅ Notebook carregado!")
            return True
            
        except Exception as e:
            self.log(f"❌ Erro ao abrir notebook: {e}", "ERROR")
            return False
    
    async def _connect_runtime(self, page) -> bool:
        """
        Conecta ao runtime do Colab (GPU)
        """
        try:
            self.log("🔌 Conectando ao runtime...")
            
            # Procurar botão de conectar
            connect_selectors = [
                'button:has-text("Connect")',
                'button:has-text("Conectar")',
                'colab-connect-button',
                '#connect'
            ]
            
            for selector in connect_selectors:
                try:
                    await page.click(selector, timeout=5000)
                    self.log(f"✅ Clicou em conectar: {selector}")
                    break
                except:
                    continue
            
            # Aguardar conexão estabelecer
            self.log("⏳ Aguardando runtime conectar...")
            await page.wait_for_timeout(10000)
            
            # Verificar se conectou (procurar indicador de RAM/Disk)
            try:
                await page.wait_for_selector('text=/RAM|Disk/', timeout=20000)
                self.log("✅ Runtime conectado!")
                return True
            except:
                self.log("⚠️ Não foi possível confirmar conexão, mas continuando...", "WARN")
                return True
            
        except Exception as e:
            self.log(f"⚠️ Erro ao conectar runtime: {e}", "WARN")
            self.log("💡 Continuando mesmo assim...")
            return True
    
    async def _execute_all_cells(self, page) -> bool:
        """
        Executa todas as células do notebook
        """
        try:
            self.log("▶️ Executando todas as células...")
            
            # Método 1: Menu Runtime > Run all
            try:
                await page.click('text=/Runtime|Ambiente de execução/')
                await page.wait_for_timeout(1000)
                await page.click('text=/Run all|Executar tudo/')
                self.log("✅ Executou via menu")
                return True
            except:
                pass
            
            # Método 2: Atalho de teclado Ctrl+F9
            try:
                await page.keyboard.press('Control+F9')
                self.log("✅ Executou via atalho (Ctrl+F9)")
                return True
            except:
                pass
            
            # Método 3: Clicar em cada célula
            try:
                cells = await page.query_selector_all('.cell')
                self.log(f"📋 Encontradas {len(cells)} células")
                
                for i, cell in enumerate(cells):
                    await cell.click()
                    await page.keyboard.press('Shift+Enter')
                    await page.wait_for_timeout(500)
                
                self.log("✅ Executou todas as células manualmente")
                return True
            except:
                pass
            
            self.log("⚠️ Não foi possível executar células", "WARN")
            return False
            
        except Exception as e:
            self.log(f"❌ Erro ao executar células: {e}", "ERROR")
            return False
    
    async def _wait_for_execution(self, page):
        """
        Aguarda execução iniciar
        """
        self.log("⏳ Aguardando execução iniciar...")
        
        try:
            # Procurar indicador de execução (spinner, progress bar, etc)
            await page.wait_for_selector('.cell-execution-indicator, .spinner', timeout=10000)
            self.log("✅ Execução iniciada!")
        except:
            self.log("💡 Execução pode ter iniciado (sem indicador visual)")
        
        await page.wait_for_timeout(5000)


async def main():
    """Ponto de entrada principal"""
    trigger = PlaywrightColabTrigger()
    
    print("=" * 60)
    print("🎭 PLAYWRIGHT COLAB TRIGGER")
    print("Automação 100% - Inicia Colab sem intervenção manual")
    print("=" * 60)
    print()
    
    success = await trigger.trigger_colab()
    
    if success:
        print()
        print("✅ SUCESSO! Colab iniciado automaticamente.")
        print("📡 Aguarde o auto-reporter enviar URL para o Gist")
        sys.exit(0)
    else:
        print()
        print("❌ FALHA! Verifique os logs acima.")
        print("💡 Considere usar Service Account como alternativa")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
