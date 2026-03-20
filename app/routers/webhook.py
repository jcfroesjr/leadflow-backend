from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.db.client import get_supabase

router = APIRouter(tags=["webhook"])

@router.post("/webhook/{empresa_id}/{token}")
async def receber_webhook(empresa_id: str, token: str, request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "erro": "Payload inválido"}, status_code=400)

    try:
        sb = get_supabase()

        # Valida token com limit(1) para evitar exceções do .single()
        result = sb.table("webhooks").select("*") \
            .eq("empresa_id", empresa_id) \
            .eq("token", token) \
            .eq("ativo", True) \
            .limit(1) \
            .execute()

        if not result.data:
            return {"ok": False, "erro": "Webhook não encontrado"}

        wh = result.data[0]

        # Mapeia campos
        mapa     = wh.get("mapeamento_campos") or {}
        nome     = payload.get(mapa.get("nome",     "nome"),     payload.get("nome",     ""))
        telefone = payload.get(mapa.get("telefone", "telefone"), payload.get("telefone", ""))
        email    = payload.get(mapa.get("email",    "email"),    payload.get("email",    ""))

        # Salva lead
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
