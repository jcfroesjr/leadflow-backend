from celery import Celery
from celery.schedules import crontab
import os

app = Celery(
    "leadflow",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379"),
    include=[
        "app.tasks.followup_tasks",
        "app.tasks.agendamento_tasks",
    ]
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

app.conf.beat_schedule = {
    "verificar-followups": {
        "task": "app.tasks.followup_tasks.verificar_followups_pendentes",
        "schedule": crontab(minute="*/15"),
    },
    "limpar-agendamentos-antigos": {
        "task": "app.tasks.agendamento_tasks.limpar_agendamentos_antigos",
        "schedule": crontab(hour=2, minute=0),
    },
}
