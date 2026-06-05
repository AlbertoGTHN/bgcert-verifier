"""Celery application for background certificate processing."""
from celery import Celery
from app.config import settings

celery_app = Celery(
    "iccbpo_cert_checker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.process_certificate"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "app.tasks.process_certificate.*": {"queue": "certificates"},
    },
    task_soft_time_limit=300,
    task_time_limit=600,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
