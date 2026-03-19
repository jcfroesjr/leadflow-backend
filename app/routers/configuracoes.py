from fastapi import APIRouter, Depends
from app.db.client import get_supabase
from app.auth import get_current_empresa_id

router = APIRouter(prefix="/configuracoes", tags=["configuracoes"])

@router.get("/")
async def get_config(empresa_id: str = Depends(get_current_empresa_id)):
    sb = get_supabase()
    res = sb.table("empresas").select("config_apis, config_agendamento, config_ia") \
        .eq("id", empresa_id).single().execute()
    return res.data or {}

@router.post("/api-keys")
async def salvar_api_keys(
    body: dict,
    empresa_id: str = Depends(get_current_empresa_id)
):
    sb = get_supabase()
    sb.table("empresas").update({
        "config_apis": body,
        "evolution_instancia": body.get("evolution_instancia", "")
    }).eq("id", empresa_id).execute()
    return {"ok": True, "mensagem": "Configurações salvas com sucesso!"}

@router.post("/empresa")
async def salvar_empresa(
    body: dict,
    empresa_id: str = Depends(get_current_empresa_id)
):
    sb = get_supabase()
    sb.table("empresas").update({
        "nome": body.get("nome"),
        "cnpj": body.get("cnpj"),
        "fuso": body.get("fuso"),
    }).eq("id", empresa_id).execute()
    return {"ok": True, "mensagem": "Empresa salva com sucesso!"}
