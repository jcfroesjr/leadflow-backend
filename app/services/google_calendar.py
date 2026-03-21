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


def _freebusy(service, calendar_ids: list, time_min: datetime, time_max: datetime) -> list:
    """Usa a API Freebusy para obter períodos ocupados em múltiplos calendários."""
    body = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "items": [{"id": cid} for cid in calendar_ids],
    }
    resp = service.freebusy().query(body=body).execute()
    ocupados = []
    for cal_data in resp.get("calendars", {}).values():
        for periodo in cal_data.get("busy", []):
            ocupados.append((
                datetime.fromisoformat(periodo["start"]),
                datetime.fromisoformat(periodo["end"]),
            ))
    return ocupados


def buscar_horarios_livres(
    credentials_dict: dict,
    calendar_id: str,
    calendars_verificar: list = None,
    fuso: str = "America/Sao_Paulo",
    dias: int = 3,
    hora_inicio_dia: int = 8,
    hora_fim_dia: int = 18,
    duracao_minutos: int = 60,
) -> list[str]:
    """
    Retorna lista de horários livres para os próximos `dias` dias ÚTEIS,
    verificando TODOS os calendários em `calendars_verificar`.
    Formato: 'DD/MM HH:MM' (ex: '22/03 14:00').
    """
    service = _build_service(credentials_dict)
    tz = ZoneInfo(fuso)
    hoje = datetime.now(tz)

    # Calendários a verificar: o principal + todos os adicionais
    ids_verificar = list({calendar_id} | set(calendars_verificar or []))

    slots_livres = []
    dias_uteis_vistos = 0
    dia_atual = hoje.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    while dias_uteis_vistos < dias and len(slots_livres) < 8:
        if dia_atual.weekday() >= 5:
            dia_atual += timedelta(days=1)
            continue

        dias_uteis_vistos += 1
        time_min = dia_atual.replace(hour=hora_inicio_dia, minute=0, second=0, microsecond=0)
        time_max = dia_atual.replace(hour=hora_fim_dia,    minute=0, second=0, microsecond=0)

        ocupados = _freebusy(service, ids_verificar, time_min, time_max)

        slot = time_min
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
    calendars_verificar: list = None,
    duracao_minutos: int = 60,
    fuso: str = "America/Sao_Paulo",
) -> bool:
    """Verifica se um slot está livre em TODOS os calendários configurados."""
    service = _build_service(credentials_dict)
    tz = ZoneInfo(fuso)
    inicio = datetime.strptime(f"{data} {hora_inicio}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    fim = inicio + timedelta(minutes=duracao_minutos)

    ids_verificar = list({calendar_id} | set(calendars_verificar or []))
    ocupados = _freebusy(service, ids_verificar, inicio, fim)
    return len(ocupados) == 0


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
