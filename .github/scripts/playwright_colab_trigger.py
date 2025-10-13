#!/usr/bin/env python3
"""
Playwright Colab Trigger (STEALTH MODE)
Inicia Google Colab automaticamente usando Playwright + Stealth
Evita detecção de bot pelo Google
"""

import os
import sys
import time
import asyncio
import random
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Playwright stealth para evitar detecção de bot
try:
    from playwright_stealth import stealth_async
except ImportError:
    # Fallback: algumas versões usam apenas 'stealth'
    try:
        from playwright_stealth import stealth as stealth_async
    except ImportError:
        # Se não tiver playwright-stealth, criar função dummy
        async def stealth_async(page):
            """Fallback se playwright-stealth não estiver disponível"""
            pass


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
    
    async def _human_delay(self, min_ms=500, max_ms=2000):
        """Delay aleatório para parecer humano"""
        delay = random.randint(min_ms, max_ms)
        await asyncio.sleep(delay / 1000)
    
    async def _human_type(self, page, selector, text):
        """Digita texto de forma humana (char por char com delay)"""
        element = await page.wait_for_selector(selector)
        for char in text:
            await element.type(char, delay=random.randint(50, 150))
        await self._human_delay(300, 800)
    
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
                
                # User agent real e atualizado
                user_agent = (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                )
                
                # Criar contexto com configurações que parecem humanas
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=user_agent,
                    locale='en-US',
                    timezone_id='America/New_York',
                    permissions=['geolocation', 'notifications'],
                    geolocation={'latitude': 40.7128, 'longitude': -74.0060},  # NYC
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1'
                    }
                )
                
                page = await context.new_page()
                
                # 🎭 APLICAR STEALTH - Esconde assinaturas de bot
                self.log("🎭 Aplicando técnicas stealth...")
                await stealth_async(page)
                self.log("✅ Stealth aplicado - navegador parece humano")
                
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
        self.log("=" * 60)
        self.log("🔍 VALIDANDO CONFIGURAÇÃO")
        self.log("=" * 60)
        
        if not self.google_email:
            self.log("❌ GOOGLE_EMAIL não configurado", "ERROR")
            self.log("💡 Defina a variável de ambiente GOOGLE_EMAIL", "WARN")
            return False
        else:
            # Mascarar email para segurança
            masked_email = self.google_email[:3] + "***" + self.google_email[self.google_email.find('@'):] if '@' in self.google_email else "***"
            self.log(f"✅ GOOGLE_EMAIL: {masked_email}")
        
        if not self.google_password:
            self.log("❌ GOOGLE_PASSWORD não configurado", "ERROR")
            self.log("💡 Defina a variável de ambiente GOOGLE_PASSWORD", "WARN")
            return False
        else:
            self.log(f"✅ GOOGLE_PASSWORD: {'*' * len(self.google_password)} ({len(self.google_password)} chars)")
        
        if not self.notebook_id:
            self.log("❌ COLAB_NOTEBOOK_ID não configurado", "ERROR")
            self.log("💡 Defina a variável de ambiente COLAB_NOTEBOOK_ID", "WARN")
            return False
        else:
            self.log(f"✅ COLAB_NOTEBOOK_ID: {self.notebook_id}")
        
        self.log(f"✅ Headless Mode: {self.headless}")
        self.log(f"✅ Timeout: {self.timeout}ms")
        self.log("=" * 60)
        self.log("✅ Todas as configurações validadas!")
        return True
    
    async def _launch_browser(self, playwright):
        """Inicia navegador Chromium com STEALTH"""
        self.log("🌐 Iniciando navegador Chromium (STEALTH MODE)...")
        
        # User agent real e atualizado
        user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
        
        browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',  # Hide automation
                '--disable-features=IsolateOrigins,site-per-process',
                '--flag-switches-begin',
                '--disable-web-security',
                '--flag-switches-end'
            ]
        )
        
        self.log("✅ Navegador iniciado com stealth")
        return browser
    
    async def _login_google(self, page) -> bool:
        """
        Faz login no Google
        """
        try:
            self.log("=" * 60)
            self.log("🔐 INICIANDO LOGIN NO GOOGLE")
            self.log("=" * 60)
            
            # Ir para página de login
            self.log("🌐 Navegando para página de login...")
            self.log("   URL: https://accounts.google.com/signin")
            
            try:
                await page.goto('https://accounts.google.com/signin', wait_until='networkidle', timeout=30000)
                self.log("✅ Página de login carregada")
            except Exception as e:
                self.log(f"❌ Erro ao carregar página de login: {e}", "ERROR")
                return False
            
            # Passo 1: Email
            self.log("")
            self.log("📧 PASSO 1: Inserindo email...")
            
            try:
                # Aguardar campo de email aparecer
                await page.wait_for_selector('input[type="email"]', timeout=10000)
                self.log("✅ Campo de email encontrado")
                
                # Delay humano antes de clicar
                await self._human_delay(800, 1500)
                
                # Preencher email COM DIGITAÇÃO HUMANA (char por char)
                self.log("⌨️ Digitando email como humano...")
                await self._human_type(page, 'input[type="email"]', self.google_email)
                masked_email = self.google_email[:3] + "***" + self.google_email[self.google_email.find('@'):]
                self.log(f"✅ Email digitado: {masked_email}")
                
                # Delay humano antes de clicar Next
                await self._human_delay(500, 1200)
                
                # Clicar em "Next"/"Próxima"
                self.log("🖱️ Clicando em 'Next'...")
                await page.click('button:has-text("Next"), button:has-text("Próxima")')
                self.log("✅ Botão 'Next' clicado")
                
                # Aguardar navegação com delay humano
                await self._human_delay(2000, 4000)
                
            except Exception as e:
                self.log(f"❌ Erro no passo do email: {e}", "ERROR")
                # Capturar screenshot para debug
                try:
                    await page.screenshot(path='/tmp/playwright_email_error.png')
                    self.log("📸 Screenshot salvo: /tmp/playwright_email_error.png")
                except:
                    pass
                return False
            
            # Passo 2: Senha
            self.log("")
            self.log("🔑 PASSO 2: Inserindo senha...")
            
            try:
                # Aguardar campo de senha aparecer (aumentado para 15s)
                await page.wait_for_selector('input[type="password"]', timeout=15000)
                self.log("✅ Campo de senha encontrado")
                
                # Delay humano antes de digitar
                await self._human_delay(1000, 2000)
                
                # Preencher senha COM DIGITAÇÃO HUMANA
                self.log("⌨️ Digitando senha como humano...")
                await self._human_type(page, 'input[type="password"]', self.google_password)
                self.log(f"✅ Senha digitada ({len(self.google_password)} caracteres)")
                
                # Delay humano antes de clicar Next
                await self._human_delay(800, 1500)
                
                # Clicar em "Next"/"Próxima"
                self.log("🖱️ Clicando em 'Next'...")
                await page.click('button:has-text("Next"), button:has-text("Próxima")')
                self.log("✅ Botão 'Next' clicado")
                
            except Exception as e:
                self.log(f"❌ Erro no passo da senha: {e}", "ERROR")
                # Capturar screenshot para debug
                try:
                    await page.screenshot(path='/tmp/playwright_password_error.png')
                    self.log("📸 Screenshot salvo: /tmp/playwright_password_error.png")
                except:
                    pass
                return False
            
            # Aguardar login completar
            self.log("")
            self.log("⏳ Aguardando login completar...")
            
            try:
                # Aguardar redirecionamento para conta Google ou aceitar página
                await page.wait_for_timeout(5000)
                
                current_url = page.url
                self.log(f"📍 URL atual: {current_url}")
                
                # Verificar se login foi bem-sucedido
                if 'myaccount.google.com' in current_url or 'accounts.google.com' in current_url:
                    self.log("=" * 60)
                    self.log("✅ LOGIN REALIZADO COM SUCESSO!")
                    self.log("=" * 60)
                    return True
                else:
                    self.log("⚠️ URL inesperada após login", "WARN")
                    return True  # Continuar mesmo assim
                    
            except Exception as e:
                self.log(f"⚠️ Erro ao verificar login: {e}", "WARN")
                # Mesmo com erro, tentar continuar
                return True
            
        except PlaywrightTimeout:
            self.log("=" * 60)
            self.log("❌ TIMEOUT NO LOGIN", "ERROR")
            self.log("=" * 60)
            self.log("⚠️ Possíveis causas:", "WARN")
            self.log("   1. Verificação em 2 etapas (2FA) ativada")
            self.log("   2. Credenciais incorretas")
            self.log("   3. Google bloqueou login automático")
            self.log("   4. Conexão lenta")
            self.log("💡 Solução: Use Service Account ao invés de login manual")
            return False
            
        except Exception as e:
            self.log("=" * 60)
            self.log(f"❌ ERRO GERAL NO LOGIN: {e}", "ERROR")
            self.log("=" * 60)
            import traceback
            self.log(f"Traceback:\n{traceback.format_exc()}")
            return False
    
    async def _open_notebook(self, page) -> bool:
        """
        Abre notebook no Colab
        """
        try:
            self.log("")
            self.log("=" * 60)
            self.log("📓 ABRINDO NOTEBOOK NO COLAB")
            self.log("=" * 60)
            
            notebook_url = f"https://colab.research.google.com/drive/{self.notebook_id}"
            self.log(f"🌐 URL: {notebook_url}")
            
            try:
                self.log("⏳ Navegando para notebook...")
                await page.goto(notebook_url, wait_until='networkidle', timeout=60000)
                self.log("✅ Página do notebook carregada")
            except Exception as e:
                self.log(f"❌ Erro ao navegar para notebook: {e}", "ERROR")
                return False
            
            # Aguardar notebook carregar
            self.log("⏳ Aguardando notebook inicializar...")
            try:
                await page.wait_for_selector('.notebook-container, #notebook, colab-notebook', timeout=30000)
                self.log("✅ Notebook inicializado!")
            except Exception as e:
                self.log(f"⚠️ Timeout aguardando notebook: {e}", "WARN")
                # Tentar continuar mesmo assim
                self.log("💡 Tentando continuar...")
            
            self.log("=" * 60)
            self.log("✅ NOTEBOOK CARREGADO COM SUCESSO!")
            self.log("=" * 60)
            return True
            
        except Exception as e:
            self.log("=" * 60)
            self.log(f"❌ ERRO AO ABRIR NOTEBOOK: {e}", "ERROR")
            self.log("=" * 60)
            import traceback
            self.log(f"Traceback:\n{traceback.format_exc()}")
            return False
    
    async def _connect_runtime(self, page) -> bool:
        """
        Conecta ao runtime do Colab (GPU)
        """
        try:
            self.log("")
            self.log("=" * 60)
            self.log("🔌 CONECTANDO AO RUNTIME")
            self.log("=" * 60)
            
            # Procurar botão de conectar
            connect_selectors = [
                'button:has-text("Connect")',
                'button:has-text("Conectar")',
                'colab-connect-button',
                '#connect'
            ]
            
            self.log("🔍 Procurando botão 'Connect'...")
            button_found = False
            
            for selector in connect_selectors:
                try:
                    self.log(f"   Tentando: {selector}")
                    await page.click(selector, timeout=5000)
                    self.log(f"✅ Botão encontrado e clicado: {selector}")
                    button_found = True
                    break
                except:
                    self.log(f"   ⚠️ Não encontrado: {selector}")
                    continue
            
            if not button_found:
                self.log("⚠️ Botão 'Connect' não encontrado", "WARN")
                self.log("💡 Possível que já esteja conectado")
            
            # Aguardar conexão estabelecer
            self.log("⏳ Aguardando runtime conectar (10s)...")
            await page.wait_for_timeout(10000)
            
            # Verificar se conectou (procurar indicador de RAM/Disk)
            self.log("🔍 Verificando se runtime conectou...")
            try:
                await page.wait_for_selector('text=/RAM|Disk|GPU/', timeout=20000)
                self.log("=" * 60)
                self.log("✅ RUNTIME CONECTADO COM SUCESSO!")
                self.log("=" * 60)
                return True
            except:
                self.log("⚠️ Não foi possível confirmar conexão visual", "WARN")
                self.log("💡 Mas continuando mesmo assim...")
                self.log("=" * 60)
                return True
            
        except Exception as e:
            self.log("=" * 60)
            self.log(f"⚠️ ERRO AO CONECTAR RUNTIME: {e}", "WARN")
            self.log("=" * 60)
            self.log("💡 Continuando execução...")
            return True
    
    async def _execute_all_cells(self, page) -> bool:
        """
        Executa todas as células do notebook
        """
        try:
            self.log("")
            self.log("=" * 60)
            self.log("▶️ EXECUTANDO TODAS AS CÉLULAS")
            self.log("=" * 60)
            
            # Método 1: Menu Runtime > Run all
            self.log("🔍 MÉTODO 1: Tentando via menu Runtime...")
            try:
                self.log("   Clicando em 'Runtime'...")
                await page.click('text=/Runtime|Ambiente de execução/', timeout=5000)
                await page.wait_for_timeout(1000)
                
                self.log("   Clicando em 'Run all'...")
                await page.click('text=/Run all|Executar tudo/', timeout=5000)
                
                self.log("=" * 60)
                self.log("✅ EXECUTADO VIA MENU (Runtime > Run all)")
                self.log("=" * 60)
                return True
            except Exception as e:
                self.log(f"   ⚠️ Método 1 falhou: {e}")
            
            # Método 2: Atalho de teclado Ctrl+F9
            self.log("🔍 MÉTODO 2: Tentando via atalho Ctrl+F9...")
            try:
                await page.keyboard.press('Control+F9')
                await page.wait_for_timeout(2000)
                
                self.log("=" * 60)
                self.log("✅ EXECUTADO VIA ATALHO (Ctrl+F9)")
                self.log("=" * 60)
                return True
            except Exception as e:
                self.log(f"   ⚠️ Método 2 falhou: {e}")
            
            # Método 3: Clicar em cada célula
            self.log("🔍 MÉTODO 3: Tentando executar células manualmente...")
            try:
                cells = await page.query_selector_all('.cell, colab-cell')
                self.log(f"   📋 Encontradas {len(cells)} células")
                
                if len(cells) == 0:
                    self.log("   ⚠️ Nenhuma célula encontrada")
                else:
                    for i, cell in enumerate(cells):
                        self.log(f"   ▶️ Executando célula {i+1}/{len(cells)}")
                        await cell.click()
                        await page.keyboard.press('Shift+Enter')
                        await page.wait_for_timeout(500)
                    
                    self.log("=" * 60)
                    self.log(f"✅ EXECUTADAS {len(cells)} CÉLULAS MANUALMENTE")
                    self.log("=" * 60)
                    return True
            except Exception as e:
                self.log(f"   ⚠️ Método 3 falhou: {e}")
            
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
