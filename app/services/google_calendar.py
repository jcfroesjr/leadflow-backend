"""
Serviço Google Calendar — cria eventos e consulta horários livres via service account.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build


_SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _build_service(credentials_dict: dict):
    creds = service_account.Credentials.from_service_account_info(
        credentials_dict, scopes=_SCOPES
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _eventos_ocupados_do_dia(service, calendar_id: str, dia: datetime, hora_inicio: int, hora_fim: int, tz) -> list:
    """Retorna lista de (inicio, fim) dos eventos ocupados em um dia."""
    time_min = dia.replace(hour=hora_inicio, minute=0, second=0, microsecond=0)
    time_max = dia.replace(hour=hora_fim,    minute=0, second=0, microsecond=0)
    resp = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min.isoformat(),
        timeMax=time_max.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    ocupados = []
    for ev in resp.get("items", []):
        inicio_ev = ev.get("start", {}).get("dateTime")
        fim_ev    = ev.get("end",   {}).get("dateTime")
        if inicio_ev and fim_ev:
            ocupados.append((
                datetime.fromisoformat(inicio_ev).astimezone(tz),
                datetime.fromisoformat(fim_ev).astimezone(tz),
            ))
    return ocupados


def buscar_horarios_livres(
    credentials_dict: dict,
    calendar_id: str,
    fuso: str = "America/Sao_Paulo",
    dias: int = 3,
    hora_inicio_dia: int = 8,
    hora_fim_dia: int = 18,
    duracao_minutos: int = 60,
) -> list[str]:
    """
    Retorna lista de horários livres para os próximos `dias` dias ÚTEIS,
    no formato 'DD/MM HH:MM' (ex: '22/03 14:00').
    """
    service = _build_service(credentials_dict)
    tz = ZoneInfo(fuso)
    hoje = datetime.now(tz)

    slots_livres = []
    dias_uteis_vistos = 0
    dia_atual = hoje.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)  # começa amanhã

    while dias_uteis_vistos < dias and len(slots_livres) < 8:
        # Pula finais de semana
        if dia_atual.weekday() >= 5:
            dia_atual += timedelta(days=1)
            continue

        dias_uteis_vistos += 1
        ocupados = _eventos_ocupados_do_dia(service, calendar_id, dia_atual, hora_inicio_dia, hora_fim_dia, tz)

        slot = dia_atual.replace(hour=hora_inicio_dia, minute=0, second=0, microsecond=0)
        time_max = dia_atual.replace(hour=hora_fim_dia, minute=0, second=0, microsecond=0)

        while slot + timedelta(minutes=duracao_minutos) <= time_max:
            slot_fim = slot + timedelta(minutes=duracao_minutos)
            livre = all(slot_fim <= oc[0] or slot >= oc[1] for oc in ocupados)
            if livre:
                slots_livres.append(slot.strftime("%d/%m %H:%M"))
            slot += timedelta(minutes=60)

        dia_atual += timedelta(days=1)

    return slots_livres[:8]


def verificar_slot_livre(
    credentials_dict: dict,
    calendar_id: str,
    data: str,
    hora_inicio: str,
    duracao_minutos: int = 60,
    fuso: str = "America/Sao_Paulo",
) -> bool:
    """Verifica se um slot específico está livre no Google Agenda."""
    service = _build_service(credentials_dict)
    tz = ZoneInfo(fuso)
    inicio = datetime.strptime(f"{data} {hora_inicio}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    fim = inicio + timedelta(minutes=duracao_minutos)

    resp = service.events().list(
        calendarId=calendar_id,
        timeMin=inicio.isoformat(),
        timeMax=fim.isoformat(),
        singleEvents=True,
    ).execute()

    return len(resp.get("items", [])) == 0


def criar_evento_calendar(
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
    service = _build_service(credentials_dict)

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
