from __future__ import annotations

from celery import shared_task


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def processar_arquivo_retorno(self, arquivo_retorno_id: int):
    from .services import ArquivoRetornoService

    service = ArquivoRetornoService()
    try:
        service.processar(arquivo_retorno_id)
    except Exception as exc:
        raise self.retry(exc=exc)
