"""Celery tasks for certificate processing."""
import asyncio
import uuid
from app.celery_app import celery_app
from loguru import logger


@celery_app.task(
    name="app.tasks.process_certificate.process",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def process_certificate_task(self, cert_id: str, file_path: str):
    """Celery task to process a certificate asynchronously."""
    from app.services.certificate_processor import CertificateProcessor
    from app.database import AsyncSessionLocal

    async def _run():
        processor = CertificateProcessor()
        async with AsyncSessionLocal() as db:
            await processor.process(uuid.UUID(cert_id), file_path, db)

    try:
        asyncio.run(_run())
        logger.info(f"Task completed for cert {cert_id}")
    except Exception as exc:
        logger.error(f"Task failed for cert {cert_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)
