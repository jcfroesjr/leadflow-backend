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


def buscar_horarios_livres(
    credentials_dict: dict,
    calendar_id: str,
    fuso: str = "America/Sao_Paulo",
    dias: int = 2,
    hora_inicio_dia: int = 8,
    hora_fim_dia: int = 18,
    duracao_minutos: int = 60,
) -> list[str]:
    """
    Retorna lista de horários livres para os próximos `dias` dias úteis,
    no formato 'DD/MM HH:MM' (ex: '22/03 14:00').
    """
    service = _build_service(credentials_dict)
    tz = ZoneInfo(fuso)
    hoje = datetime.now(tz)

    slots_livres = []
    dia_atual = hoje.replace(hour=0, minute=0, second=0, microsecond=0)

    for _ in range(dias):
        # Pula finais de semana
        if dia_atual.weekday() >= 5:
            dia_atual += timedelta(days=1)
            continue

        time_min = dia_atual.replace(hour=hora_inicio_dia, minute=0)
        time_max = dia_atual.replace(hour=hora_fim_dia, minute=0)

        # Busca eventos do dia
        eventos_resp = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        ocupados = []
        for ev in eventos_resp.get("items", []):
            inicio_ev = ev.get("start", {}).get("dateTime")
            fim_ev = ev.get("end", {}).get("dateTime")
            if inicio_ev and fim_ev:
                ocupados.append((
                    datetime.fromisoformat(inicio_ev).astimezone(tz),
                    datetime.fromisoformat(fim_ev).astimezone(tz),
                ))

        # Gera slots de 1h e verifica disponibilidade
        slot = time_min
        while slot + timedelta(minutes=duracao_minutos) <= time_max:
            slot_fim = slot + timedelta(minutes=duracao_minutos)
            livre = all(slot_fim <= oc[0] or slot >= oc[1] for oc in ocupados)
            # Não sugere horários já passados
            if livre and slot > hoje:
                slots_livres.append(slot.strftime("%d/%m %H:%M"))
            slot += timedelta(minutes=60)

        dia_atual += timedelta(days=1)

    return slots_livres[:8]  # máximo 8 opções


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
