"""Celery worker configuration and initialization."""
from celery import Celery
from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "qsearch",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.process"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes
    task_soft_time_limit=1500,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)
