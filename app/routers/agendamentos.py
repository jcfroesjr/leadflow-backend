"""
Router de Agendamentos — OAuth2 Google Calendar e configurações.
"""
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from app.db.client import get_supabase

router = APIRouter(prefix="/agendamentos", tags=["agendamentos"])

SCOPES = ["https://www.googleapis.com/auth/calendar"]
FRONTEND_URL = "https://leadflow-frontend.bqvcbz.easypanel.host"
BACKEND_URL  = "https://leadflow-backend.bqvcbz.easypanel.host"
REDIRECT_URI = f"{BACKEND_URL}/agendamentos/oauth/google/callback"


def _get_oauth_client_config(config_apis: dict) -> dict:
    return {
        "web": {
            "client_id":     config_apis.get("google_oauth_client_id", ""),
            "client_secret": config_apis.get("google_oauth_client_secret", ""),
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
        }
    }


@router.get("/oauth/google/url")
async def oauth_google_url(empresa_id: str = Query(...)):
    """Gera a URL de autorização OAuth2 do Google Calendar."""
    sb = get_supabase()
    res = sb.table("empresas").select("config_apis").eq("id", empresa_id).limit(1).execute()
    if not res.data:
        return JSONResponse({"ok": False, "erro": "Empresa não encontrada"}, status_code=404)

    config_apis = res.data[0].get("config_apis") or {}
    client_id     = config_apis.get("google_oauth_client_id", "")
    client_secret = config_apis.get("google_oauth_client_secret", "")

    if not client_id or not client_secret:
        return JSONResponse(
            {"ok": False, "erro": "Configure o Google OAuth Client ID e Client Secret nas Configurações → APIs"},
            status_code=400,
        )

    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(
        _get_oauth_client_config(config_apis),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=empresa_id,
    )
    return {"url": auth_url}


@router.get("/oauth/google/callback")
async def oauth_google_callback(
    code:  str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
):
    """Recebe o callback OAuth2 do Google e salva os tokens."""
    if error:
        return RedirectResponse(f"{FRONTEND_URL}/agendamentos?oauth_error={error}")

    empresa_id = state
    sb = get_supabase()
    res = sb.table("empresas").select("config_apis").eq("id", empresa_id).limit(1).execute()
    if not res.data:
        return RedirectResponse(f"{FRONTEND_URL}/agendamentos?oauth_error=empresa_nao_encontrada")

    config_apis = res.data[0].get("config_apis") or {}

    try:
        from google_auth_oauthlib.flow import Flow
        from googleapiclient.discovery import build

        flow = Flow.from_client_config(
            _get_oauth_client_config(config_apis),
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Busca email da conta conectada
        svc = build("oauth2", "v2", credentials=credentials)
        user_info = svc.userinfo().get().execute()
        email = user_info.get("email", "")

        # Salva tokens na tabela calendario_tokens
        token_data = {
            "empresa_id":    empresa_id,
            "plataforma":    "google",
            "access_token":  credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_expiry":  credentials.expiry.isoformat() if credentials.expiry else None,
            "email":         email,
        }
        sb.table("calendario_tokens").upsert(token_data, on_conflict="empresa_id,plataforma").execute()

        # Salva o email como calendar_id padrão se ainda não tiver
        if not config_apis.get("google_calendar_id") or config_apis.get("google_calendar_id") == "primary":
            config_apis["google_calendar_id"] = email
            sb.table("empresas").update({"config_apis": config_apis}).eq("id", empresa_id).execute()

        return RedirectResponse(f"{FRONTEND_URL}/agendamentos?oauth_success=google&email={email}")

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return RedirectResponse(f"{FRONTEND_URL}/agendamentos?oauth_error={str(e)[:100]}")


@router.get("/oauth/google/status")
async def oauth_google_status(empresa_id: str = Query(...)):
    """Verifica se o Google Calendar está conectado via OAuth."""
    sb = get_supabase()
    res = sb.table("calendario_tokens") \
        .select("email, token_expiry") \
        .eq("empresa_id", empresa_id) \
        .eq("plataforma", "google") \
        .limit(1).execute()

    if res.data:
        return {"conectado": True, "email": res.data[0].get("email", "")}
    return {"conectado": False}


@router.delete("/oauth/google/desconectar")
async def oauth_google_desconectar(empresa_id: str = Query(...)):
    """Remove os tokens OAuth do Google Calendar."""
    sb = get_supabase()
    sb.table("calendario_tokens") \
        .delete() \
        .eq("empresa_id", empresa_id) \
        .eq("plataforma", "google") \
        .execute()
    return {"ok": True}


@router.post("/config")
async def salvar_config_agendamento(body: dict):
    """Salva configurações de agendamento da empresa."""
    empresa_id = body.pop("empresa_id", None)
    if not empresa_id:
        return JSONResponse({"ok": False, "erro": "empresa_id obrigatório"}, status_code=400)
    sb = get_supabase()
    sb.table("empresas").update({"config_agendamento": body}).eq("id", empresa_id).execute()
    return {"ok": True}
