from fastapi import APIRouter, Depends
from app.db.client import get_supabase
from app.auth import get_current_empresa_id

router = APIRouter(prefix="/leads", tags=["leads"])

@router.get("/")
async def listar_leads(empresa_id: str = Depends(get_current_empresa_id)):
    sb = get_supabase()
    res = sb.table("leads").select("*") \
        .eq("empresa_id", empresa_id) \
        .order("criado_em", desc=True) \
        .limit(50).execute()
    return res.data or []
