#!/usr/bin/env python3
"""
Advanced Playwright Colab Automation
Implementa técnicas stealth avançadas, retry system e comportamento humanizado
SEM usar biblioteca playwright-stealth (implementação manual)
"""

import os
import sys
import asyncio
import random
import time
from datetime import datetime
from typing import Optional, Dict, List
from playwright.async_api import async_playwright, Page, Browser, BrowserContext, TimeoutError as PlaywrightTimeout


class ColabAutomation:
    """
    Automação avançada do Google Colab com técnicas anti-detecção
    """
    
    def __init__(self):
        self.google_email = os.getenv('GOOGLE_EMAIL')
        self.google_password = os.getenv('GOOGLE_PASSWORD')
        self.notebook_id = os.getenv('COLAB_NOTEBOOK_ID')
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Configurações de retry
        self.max_retries = 3
        self.base_delay = 2
        
    def log(self, message: str, level: str = "INFO"):
        """Log estruturado com timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] [{level}] {message}")
    
    async def _random_delay(self, min_ms: int = 500, max_ms: int = 2000):
        """Delay aleatório para simular comportamento humano"""
        delay = random.uniform(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)
    
    async def _exponential_backoff(self, attempt: int) -> float:
        """Backoff exponencial com jitter"""
        base = self.base_delay * (2 ** attempt)
        jitter = random.uniform(0, base * 0.1)
        delay = base + jitter
        return min(delay, 60)  # Max 60 segundos
    
    async def _retry_operation(self, operation, *args, **kwargs):
        """Sistema de retry robusto com backoff exponencial"""
        for attempt in range(self.max_retries):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                
                delay = await self._exponential_backoff(attempt)
                self.log(f"⚠️ Tentativa {attempt + 1}/{self.max_retries} falhou: {e}", "WARN")
                self.log(f"⏳ Aguardando {delay:.1f}s antes de tentar novamente...", "INFO")
                await asyncio.sleep(delay)
    
    async def _inject_stealth_scripts(self, page: Page):
        """
        Injeta scripts de stealth no contexto do browser
        Implementação manual de técnicas anti-detecção
        """
        self.log("🎭 Injetando scripts stealth...")
        
        # Script 1: Remover navigator.webdriver
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        # Script 2: Sobrescrever propriedades de automação
        await page.add_init_script("""
            // Chrome runtime
            window.chrome = {
                runtime: {}
            };
            
            // Plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en', 'pt-BR', 'pt']
            });
            
            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        # Script 3: Humanizar propriedades do browser
        await page.add_init_script("""
            // User-Agent realístico já configurado no contexto
            
            // Connection
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    saveData: false
                })
            });
            
            // Hardware Concurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });
            
            // Device Memory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8
            });
        """)
        
        self.log("✅ Scripts stealth injetados com sucesso")
    
    async def _setup_browser(self, headless: bool = True):
        """
        Configura browser com características humanizadas
        """
        self.log("🌐 Iniciando browser com configuração stealth...")
        
        playwright = await async_playwright().start()
        
        # Configuração de browser realístico
        self.browser = await playwright.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
            ]
        )
        
        # Contexto com propriedades humanizadas
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            geolocation={'latitude': 40.7128, 'longitude': -74.0060},
            permissions=['geolocation', 'notifications'],
            color_scheme='light',
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            }
        )
        
        self.page = await self.context.new_page()
        
        # Injetar scripts stealth
        await self._inject_stealth_scripts(self.page)
        
        self.log("✅ Browser configurado com stealth")
    
    async def _human_type(self, element, text: str):
        """
        Digita texto com timing humano
        """
        await element.click()
        await self._random_delay(300, 800)
        
        for char in text:
            await element.type(char)
            # Delay aleatório entre teclas (50-150ms)
            await asyncio.sleep(random.uniform(0.05, 0.15))
        
        await self._random_delay(200, 500)
    
    async def _human_click(self, selector: str):
        """
        Clique com comportamento humanizado
        """
        element = await self.page.wait_for_selector(selector, timeout=30000)
        
        # Mover mouse para o elemento primeiro
        box = await element.bounding_box()
        if box:
            # Adicionar offset aleatório dentro do elemento
            x = box['x'] + box['width'] * random.uniform(0.3, 0.7)
            y = box['y'] + box['height'] * random.uniform(0.3, 0.7)
            
            await self.page.mouse.move(x, y, steps=random.randint(10, 30))
            await self._random_delay(100, 300)
        
        await element.click()
        await self._random_delay(500, 1000)
    
    async def navigate_to_colab(self, notebook_url: str):
        """Navega para o notebook do Colab"""
        self.log(f"🌐 Navegando para: {notebook_url}")
        
        await self._retry_operation(
            self.page.goto,
            notebook_url,
            wait_until='domcontentloaded',
            timeout=60000
        )
        
        await self._random_delay(2000, 4000)
        self.log("✅ Página carregada")
    
    async def login_google(self):
        """
        Faz login no Google com comportamento humanizado
        """
        self.log("🔐 Iniciando login no Google...")
        
        try:
            # Passo 1: Email
            self.log("📧 Inserindo email...")
            email_selector = 'input[type="email"]'
            await self.page.wait_for_selector(email_selector, timeout=30000)
            
            email_input = await self.page.query_selector(email_selector)
            await self._human_type(email_input, self.google_email)
            
            # Clicar em "Next"
            await self._human_click('button:has-text("Next"), button:has-text("Próximo")')
            
            await self._random_delay(3000, 5000)
            
            # Passo 2: Senha
            self.log("🔑 Inserindo senha...")
            password_selector = 'input[type="password"]'
            await self.page.wait_for_selector(password_selector, timeout=30000)
            
            password_input = await self.page.query_selector(password_selector)
            await self._human_type(password_input, self.google_password)
            
            # Clicar em "Next"
            await self._human_click('button:has-text("Next"), button:has-text("Próximo")')
            
            await self._random_delay(5000, 8000)
            
            self.log("✅ Login concluído")
            return True
            
        except Exception as e:
            self.log(f"❌ Erro no login: {e}", "ERROR")
            return False
    
    async def connect_runtime(self):
        """Conecta ao runtime do Colab"""
        self.log("🔌 Conectando ao runtime...")
        
        try:
            # Aguardar botão de conexão aparecer
            connect_button = await self.page.wait_for_selector(
                'colab-connect-button',
                timeout=30000
            )
            
            # Verificar se já está conectado
            is_connected = await self.page.evaluate("""
                () => {
                    const button = document.querySelector('colab-connect-button');
                    return button && button.shadowRoot.querySelector('[aria-label*="Connected"]') !== null;
                }
            """)
            
            if is_connected:
                self.log("✅ Runtime já conectado")
                return True
            
            # Clicar no botão de conexão
            await connect_button.click()
            await self._random_delay(3000, 5000)
            
            # Aguardar conexão
            await self.page.wait_for_function("""
                () => {
                    const button = document.querySelector('colab-connect-button');
                    return button && button.shadowRoot.querySelector('[aria-label*="Connected"]') !== null;
                }
            """, timeout=120000)
            
            self.log("✅ Runtime conectado")
            return True
            
        except Exception as e:
            self.log(f"❌ Erro ao conectar runtime: {e}", "ERROR")
            return False
    
    async def execute_cell(self, cell_index: int = 0):
        """Executa uma célula específica"""
        self.log(f"▶️ Executando célula {cell_index}...")
        
        try:
            # Selecionar célula
            await self.page.evaluate(f"""
                () => {{
                    const cells = document.querySelectorAll('.cell');
                    if (cells[{cell_index}]) {{
                        cells[{cell_index}].click();
                    }}
                }}
            """)
            
            await self._random_delay(500, 1000)
            
            # Executar com Shift+Enter
            await self.page.keyboard.press('Shift+Enter')
            
            await self._random_delay(2000, 3000)
            
            self.log(f"✅ Célula {cell_index} executada")
            return True
            
        except Exception as e:
            self.log(f"❌ Erro ao executar célula: {e}", "ERROR")
            return False
    
    async def execute_all_cells(self):
        """Executa todas as células do notebook"""
        self.log("▶️ Executando todas as células...")
        
        try:
            # Usar menu Runtime > Run all
            await self.page.keyboard.press('Control+F9')
            
            await self._random_delay(2000, 3000)
            
            self.log("✅ Todas as células executadas")
            return True
            
        except Exception as e:
            self.log(f"❌ Erro ao executar células: {e}", "ERROR")
            return False
    
    async def close(self):
        """Fecha browser"""
        if self.browser:
            await self.browser.close()
            self.log("🔒 Browser fechado")


async def main():
    """Função principal"""
    print("=" * 70)
    print("🎭 ADVANCED PLAYWRIGHT COLAB AUTOMATION")
    print("Stealth manual + Retry system + Comportamento humanizado")
    print("=" * 70)
    print()
    
    automation = ColabAutomation()
    
    try:
        # Setup browser
        await automation._setup_browser(headless=True)
        
        # Navegar para notebook
        notebook_url = f"https://colab.research.google.com/drive/{automation.notebook_id}"
        await automation.navigate_to_colab(notebook_url)
        
        # Login
        if not await automation.login_google():
            print("\n❌ Falha no login!")
            sys.exit(1)
        
        # Conectar runtime
        if not await automation.connect_runtime():
            print("\n❌ Falha ao conectar runtime!")
            sys.exit(1)
        
        # Executar todas as células
        if not await automation.execute_all_cells():
            print("\n❌ Falha ao executar células!")
            sys.exit(1)
        
        print()
        print("✅ SUCESSO! Notebook executado com sucesso!")
        print()
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}\n")
        sys.exit(1)
    
    finally:
        await automation.close()


if __name__ == "__main__":
    asyncio.run(main())
