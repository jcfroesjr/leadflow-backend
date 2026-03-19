from fastapi import Header, HTTPException
from app.db.client import get_supabase

async def get_current_empresa_id(authorization: str = Header(None)) -> str:
    if not authorization:
        raise HTTPException(401, "Token não fornecido")
    token = authorization.replace("Bearer ", "")
    sb = get_supabase()
    user = sb.auth.get_user(token)
    if not user.user:
        raise HTTPException(401, "Token inválido")
    membro = sb.table("membros").select("empresa_id") \
        .eq("usuario_id", user.user.id).single().execute()
    if not membro.data:
        raise HTTPException(403, "Empresa não encontrada")
    return membro.data["empresa_id"]
