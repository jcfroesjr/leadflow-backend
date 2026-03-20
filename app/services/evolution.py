import httpx

async def enviar_mensagem(base_url: str, api_key: str, instancia: str, numero: str, texto: str) -> dict:
    """Envia mensagem de texto via Evolution API."""
    numero_limpo = "".join(filter(str.isdigit, numero))
    if not numero_limpo:
        return {"ok": False, "erro": "Número inválido"}

    url = f"{base_url.rstrip('/')}/message/sendText/{instancia}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    body = {"number": numero_limpo, "text": texto}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=body, headers=headers)
            return {"ok": resp.status_code < 300, "status": resp.status_code, "resposta": resp.text}
    except Exception as e:
        return {"ok": False, "erro": str(e)}
