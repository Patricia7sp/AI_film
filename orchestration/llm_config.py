"""
Configuração de LLM - Gemini 2.0 Flash como Principal
Migração de OpenAI para Google Gemini para melhor custo-benefício
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurações do LLM
DEFAULT_LLM_PROVIDER = "gemini"  # gemini ou openai
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM", "gemini-2.0-flash-exp")
FALLBACK_LLM_MODEL = os.getenv("FALLBACK_LLM", "gpt-4o-mini")

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Parâmetros de geração
GEMINI_GENERATION_CONFIG = {
    "temperature": 0.9,  # Mais criativo para prompts cinematográficos
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

OPENAI_GENERATION_CONFIG = {
    "temperature": 0.9,
    "max_tokens": 4096,
    "top_p": 0.95,
}


def get_llm_client(provider: Optional[str] = None):
    """
    Retorna o cliente LLM configurado
    
    Args:
        provider: "gemini" ou "openai". Se None, usa DEFAULT_LLM_PROVIDER
    
    Returns:
        Cliente LLM configurado (ChatGoogleGenerativeAI ou ChatOpenAI)
    """
    provider = provider or DEFAULT_LLM_PROVIDER
    
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        if not GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY não encontrada. "
                "Defina GEMINI_API_KEY ou GOOGLE_API_KEY no .env"
            )
        
        return ChatGoogleGenerativeAI(
            model=DEFAULT_LLM_MODEL,
            google_api_key=GEMINI_API_KEY,
            **GEMINI_GENERATION_CONFIG
        )
    
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        
        if not OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY não encontrada. "
                "Defina OPENAI_API_KEY no .env"
            )
        
        return ChatOpenAI(
            model=FALLBACK_LLM_MODEL,
            openai_api_key=OPENAI_API_KEY,
            **OPENAI_GENERATION_CONFIG
        )
    
    else:
        raise ValueError(f"Provider inválido: {provider}. Use 'gemini' ou 'openai'")


def get_llm_with_fallback():
    """
    Retorna LLM com fallback automático
    Tenta Gemini primeiro, se falhar usa OpenAI
    """
    try:
        return get_llm_client("gemini")
    except Exception as e:
        print(f"⚠️ Gemini falhou: {e}")
        print("🔄 Usando OpenAI como fallback...")
        return get_llm_client("openai")


# Configuração para prompts cinematográficos
CINEMATIC_PROMPT_TEMPLATE = """Você é um especialista em direção de fotografia e prompts para geração de imagens.

Tarefa: Transformar a seguinte cena em um prompt ultra-detalhado para ComfyUI/FLUX.

Cena: {scene_description}

Inclua:
1. Estilo cinematográfico específico (ex: "Blade Runner 2049 style", "Wes Anderson symmetry")
2. Iluminação detalhada (ex: "golden hour backlight", "dramatic chiaroscuro")
3. Lente e câmera (ex: "shot on ARRI Alexa, 35mm anamorphic lens")
4. Composição (ex: "rule of thirds", "dutch angle", "extreme wide shot")
5. Resolução e qualidade (ex: "8K, photorealistic, highly detailed")
6. Mood e atmosfera (ex: "melancholic", "tense", "dreamlike")

Negative prompts: {negative_prompts}

Formato de saída:
PROMPT: [prompt detalhado aqui]
NEGATIVE: [negative prompts aqui]
"""

# Custos estimados (por 1M tokens)
COST_COMPARISON = {
    "gemini-2.0-flash-exp": {
        "input": 0.075,  # $0.075 / 1M tokens
        "output": 0.30,   # $0.30 / 1M tokens
        "description": "95% mais barato que GPT-4, excelente para criatividade"
    },
    "gpt-4o-mini": {
        "input": 0.15,    # $0.15 / 1M tokens (estimado)
        "output": 0.60,   # $0.60 / 1M tokens (estimado)
        "description": "Fallback para casos específicos"
    }
}


def get_llm():
    """
    Função alias para get_llm_client para compatibilidade
    """
    return get_llm_client()


def generate_cinematic_prompt(story_text: str):
    """
    Gera prompt cinematográfico a partir do texto da história
    
    Args:
        story_text: Texto da história
        
    Returns:
        Prompt cinematográfico detalhado para geração de imagens
    """
    try:
        llm = get_llm_with_fallback()
        
        prompt = f"""
Transforme esta história em um prompt cinematográfico ultra-detalhado para geração de imagens:

HISTÓRIA:
{story_text}

Crie um prompt que inclua:
1. Estilo cinematográfico específico (ex: "Blade Runner 2049 style", "Wes Anderson symmetry")
2. Iluminação detalhada (ex: "golden hour backlight", "dramatic chiaroscuro")
3. Lente e câmera (ex: "shot on ARRI Alexa, 35mm anamorphic lens")
4. Composição (ex: "rule of thirds", "dutch angle", "extreme wide shot")
5. Resolução e qualidade (ex: "8K, photorealistic, highly detailed")
6. Mood e atmosfera (ex: "melancholic", "tense", "dreamlike")

Retorne apenas o prompt final, sem formatação adicional.
"""
        
        response = llm.invoke(prompt)
        return response.content.strip()
        
    except Exception as e:
        print(f"⚠️ Erro ao gerar prompt cinematográfico: {e}")
        # Fallback para prompt simples
        return f"Cinematic scene based on: {story_text[:100]}..., photorealistic, highly detailed, 8K"


def print_llm_config():
    """Imprime configuração atual do LLM"""
    print("=" * 70)
    print("🤖 CONFIGURAÇÃO DO LLM")
    print("=" * 70)
    print(f"Provider Principal: {DEFAULT_LLM_PROVIDER}")
    print(f"Modelo Principal: {DEFAULT_LLM_MODEL}")
    print(f"Modelo Fallback: {FALLBACK_LLM_MODEL}")
    print(f"Gemini API Key: {'✅ Configurada' if GEMINI_API_KEY else '❌ Não encontrada'}")
    print(f"OpenAI API Key: {'✅ Configurada' if OPENAI_API_KEY else '❌ Não encontrada'}")
    print("=" * 70)
    print("\n💰 ECONOMIA ESTIMADA:")
    print(f"Usando Gemini: ~95% mais barato que GPT-4")
    print(f"Custo Gemini Input: ${COST_COMPARISON['gemini-2.0-flash-exp']['input']}/1M tokens")
    print(f"Custo Gemini Output: ${COST_COMPARISON['gemini-2.0-flash-exp']['output']}/1M tokens")
    print("=" * 70)


if __name__ == "__main__":
    print_llm_config()
    
    # Testar conexão
    try:
        llm = get_llm_with_fallback()
        print("\n✅ LLM configurado com sucesso!")
        print(f"Modelo: {llm.model_name if hasattr(llm, 'model_name') else 'N/A'}")
    except Exception as e:
        print(f"\n❌ Erro ao configurar LLM: {e}")
