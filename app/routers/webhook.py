import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.db.client import get_supabase

router = APIRouter(tags=["webhook"])

@router.post("/webhook/{empresa_id}/{token}")
async def receber_webhook(empresa_id: str, token: str, request: Request):
    # Lê o body raw e tenta decodificar com UTF-8, fallback para latin-1
    try:
        body = await request.body()
        try:
            payload = json.loads(body.decode("utf-8"))
        except UnicodeDecodeError:
            payload = json.loads(body.decode("latin-1"))
    except Exception as e:
        return JSONResponse({"ok": False, "erro": f"Payload inválido: {str(e)}"}, status_code=400)

    try:
        sb = get_supabase()

        result = sb.table("webhooks").select("*") \
            .eq("empresa_id", empresa_id) \
            .eq("token", token) \
            .eq("ativo", True) \
            .limit(1) \
            .execute()

        if not result.data:
            return {"ok": False, "erro": "Webhook não encontrado"}

        wh = result.data[0]

        mapa     = wh.get("mapeamento_campos") or {}
        nome     = payload.get(mapa.get("nome",     "nome"),     payload.get("nome",     ""))
        telefone = payload.get(mapa.get("telefone", "telefone"), payload.get("telefone", ""))
        email    = payload.get(mapa.get("email",    "email"),    payload.get("email",    ""))

        sb.table("leads").insert({
            "empresa_id": empresa_id,
            "nome":       nome,
            "telefone":   telefone,
            "email":      email,
            "origem":     wh.get("plataforma", "webhook"),
            "status":     "pendente",
            "dados_raw":  payload,
        }).execute()

        return {"ok": True}

    except Exception as e:
        return JSONResponse({"ok": False, "erro": str(e)}, status_code=500)
