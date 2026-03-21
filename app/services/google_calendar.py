"""
Serviço Google Calendar — cria eventos usando service account.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build


_SCOPES = ["https://www.googleapis.com/auth/calendar"]


def criar_evento(
    credentials_dict: dict,
    calendar_id: str,
    titulo: str,
    data: str,
    hora_inicio: str,
    duracao_minutos: int = 60,
    descricao: str = "",
    fuso: str = "America/Sao_Paulo",
) -> dict:
    """
    Cria evento no Google Agenda.
    data: YYYY-MM-DD
    hora_inicio: HH:MM
    Retorna dict com 'link' e 'evento_id'.
    """
    creds = service_account.Credentials.from_service_account_info(
        credentials_dict, scopes=_SCOPES
    )
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    tz = ZoneInfo(fuso)
    inicio = datetime.strptime(f"{data} {hora_inicio}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    fim = inicio + timedelta(minutes=duracao_minutos)

    event = {
        "summary": titulo,
        "description": descricao,
        "start": {"dateTime": inicio.isoformat(), "timeZone": fuso},
        "end":   {"dateTime": fim.isoformat(),    "timeZone": fuso},
    }

    resultado = service.events().insert(calendarId=calendar_id, body=event).execute()
    return {
        "evento_id": resultado.get("id", ""),
        "link":      resultado.get("htmlLink", ""),
    }
