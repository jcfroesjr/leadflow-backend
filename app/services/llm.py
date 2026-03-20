"""
Serviço LLM unificado — suporta Anthropic Claude, Google Gemini e OpenAI GPT.
"""
import os


def _get_provider(modelo: str) -> str:
    if modelo.startswith("gemini"):
        return "gemini"
    if modelo.startswith("claude"):
        return "anthropic"
    return "openai"


async def gerar_resposta(
    modelo: str,
    system_prompt: str,
    mensagem: str,
    api_key: str = "",
    temperatura: float = 0.7,
    max_tokens: int = 500,
    provider: str = "",
) -> str:
    provider = provider or _get_provider(modelo)

    # ── Google Gemini ─────────────────────────────────────────────────────────
    if provider == "gemini":
        from google import genai
        from google.genai import types

        key = api_key or os.getenv("GEMINI_API_KEY", "")
        client = genai.Client(api_key=key)

        resp = await client.aio.models.generate_content(
            model=modelo,
            contents=mensagem,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperatura,
                max_output_tokens=max_tokens,
            ),
        )
        return resp.text or ""

    # ── OpenAI GPT ────────────────────────────────────────────────────────────
    if provider == "openai":
        from openai import AsyncOpenAI

        key = api_key or os.getenv("OPENAI_API_KEY", "")
        client = AsyncOpenAI(api_key=key)

        resp = await client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": mensagem},
            ],
            temperature=temperatura,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    # ── Anthropic Claude (padrão) ─────────────────────────────────────────────
    import anthropic

    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    client = anthropic.AsyncAnthropic(api_key=key)

    resp = await client.messages.create(
        model=modelo,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": mensagem}],
        temperature=temperatura,
    )
    return resp.content[0].text if resp.content else ""
