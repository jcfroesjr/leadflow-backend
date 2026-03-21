"""
Router de Agenda — espelho do Google Calendar para o frontend.
"""
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.db.client import get_supabase

router = APIRouter(prefix="/agenda", tags=["agenda"])


@router.get("/google/eventos")
async def listar_eventos(
    empresa_id: str = Query(...),
    data_inicio: str = Query(None),   # YYYY-MM-DD
    data_fim: str = Query(None),      # YYYY-MM-DD
):
    """Retorna eventos do Google Calendar da empresa para o intervalo informado."""
    sb = get_supabase()
    res = sb.table("empresas") \
        .select("config_apis, fuso") \
        .eq("id", empresa_id).limit(1).execute()

    if not res.data:
        return JSONResponse({"ok": False, "erro": "Empresa não encontrada"}, status_code=404)

    empresa = res.data[0]
    config_apis = empresa.get("config_apis") or {}
    fuso = empresa.get("fuso") or "America/Sao_Paulo"
    creds = config_apis.get("google_calendar_credentials")
    calendar_id = config_apis.get("google_calendar_id", "primary")

    if not creds:
        return JSONResponse({"ok": False, "erro": "Credenciais Google Calendar não configuradas"}, status_code=400)

    tz = ZoneInfo(fuso)
    hoje = datetime.now(tz)

    if data_inicio:
        inicio = datetime.strptime(data_inicio, "%Y-%m-%d").replace(tzinfo=tz)
    else:
        # Início da semana atual (segunda-feira)
        inicio = (hoje - timedelta(days=hoje.weekday())).replace(hour=0, minute=0, second=0)

    if data_fim:
        fim = datetime.strptime(data_fim, "%Y-%m-%d").replace(tzinfo=tz, hour=23, minute=59, second=59)
    else:
        fim = inicio + timedelta(days=7)

    try:
        from app.services.google_calendar import _build_service

        eventos_raw = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _build_service(creds).events().list(
                calendarId=calendar_id,
                timeMin=inicio.isoformat(),
                timeMax=fim.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=100,
            ).execute()
        )

        eventos = []
        for ev in eventos_raw.get("items", []):
            start = ev.get("start", {})
            end = ev.get("end", {})
            eventos.append({
                "id":        ev.get("id"),
                "titulo":    ev.get("summary", "(sem título)"),
                "descricao": ev.get("description", ""),
                "inicio":    start.get("dateTime") or start.get("date"),
                "fim":       end.get("dateTime") or end.get("date"),
                "dia_inteiro": "date" in start,
                "link":      ev.get("htmlLink", ""),
                "status":    ev.get("status", ""),
            })

        return {"ok": True, "eventos": eventos, "fuso": fuso}

    except Exception as e:
        return JSONResponse({"ok": False, "erro": str(e)}, status_code=500)
