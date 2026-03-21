import httpx


def _limpar_numero(numero: str) -> str:
    return "".join(filter(str.isdigit, numero))


async def enviar_mensagem(base_url: str, api_key: str, instancia: str, numero: str, texto: str) -> dict:
    """Envia mensagem de texto via Evolution API."""
    numero_limpo = _limpar_numero(numero)
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


async def enviar_contato(
    base_url: str,
    api_key: str,
    instancia: str,
    numero_destino: str,
    nome_contato: str,
    numero_contato: str,
) -> dict:
    """Envia cartão de contato WhatsApp — ao tocar abre conversa diretamente."""
    numero_destino = _limpar_numero(numero_destino)
    numero_contato = _limpar_numero(numero_contato)
    if not numero_destino or not numero_contato:
        return {"ok": False, "erro": "Número inválido"}

    url = f"{base_url.rstrip('/')}/message/sendContact/{instancia}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    body = {
        "number": numero_destino,
        "contact": [
            {
                "fullName": nome_contato or numero_contato,
                "wuid": f"{numero_contato}@s.whatsapp.net",
                "phoneNumber": f"+{numero_contato}",
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=body, headers=headers)
            return {"ok": resp.status_code < 300, "status": resp.status_code}
    except Exception as e:
        return {"ok": False, "erro": str(e)}


async def enviar_documento(
    base_url: str,
    api_key: str,
    instancia: str,
    numero: str,
    base64_data: str,
    nome_arquivo: str = "lead.pdf",
    caption: str = "",
) -> dict:
    """Envia documento (PDF) em base64 via Evolution API."""
    numero_limpo = _limpar_numero(numero)
    if not numero_limpo:
        return {"ok": False, "erro": "Número inválido"}

    url = f"{base_url.rstrip('/')}/message/sendMedia/{instancia}"
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    body = {
        "number": numero_limpo,
        "mediatype": "document",
        "mimetype": "application/pdf",
        "fileName": nome_arquivo,
        "caption": caption,
        "media": base64_data,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=body, headers=headers)
            return {"ok": resp.status_code < 300, "status": resp.status_code, "resposta": resp.text}
    except Exception as e:
        return {"ok": False, "erro": str(e)}
