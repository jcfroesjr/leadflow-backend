from fastapi import APIRouter, Request
from app.db.client import get_supabase

router = APIRouter(tags=["webhook"])

@router.post("/webhook/{empresa_id}/{token}")
async def receber_webhook(empresa_id: str, token: str, request: Request):
    payload = await request.json()
    sb = get_supabase()

    # Valida token — usa maybeSingle para não lançar exceção quando não encontrado
    result = sb.table("webhooks").select("*") \
        .eq("empresa_id", empresa_id) \
        .eq("token", token) \
        .eq("ativo", True) \
        .maybe_single().execute()

    if not result or not result.data:
        return {"ok": False, "erro": "Webhook não encontrado"}

    wh = result.data

    # Mapeia campos
    mapa = wh.get("mapeamento_campos") or {}
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
