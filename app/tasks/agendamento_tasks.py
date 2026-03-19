from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task
def limpar_agendamentos_antigos():
    logger.info("Limpando agendamentos antigos...")
    return {"ok": True}
