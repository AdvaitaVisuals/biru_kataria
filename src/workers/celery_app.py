"""
Celery App Configuration — The Engine Room

- Broker: Redis (docker-compose provides it)
- Result Backend: Redis
- Heavy work (video processing) runs HERE, never on the API server
"""

from celery import Celery
from src.config import settings

celery_app = Celery(
    "biru_bhai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="Asia/Kolkata",
    enable_utc=True,

    # Task behavior
    task_track_started=True,
    task_acks_late=True,           # Re-queue if worker crashes mid-task
    worker_prefetch_multiplier=1,  # Only grab 1 task at a time (heavy tasks)

    # Result expiry
    result_expires=3600,  # 1 hour

    # Task routes — organize by weight
    task_routes={
        "src.workers.tasks.process_asset": {"queue": "heavy"},
        "src.workers.tasks.transcribe_asset": {"queue": "heavy"},
        "src.workers.tasks.cut_clips": {"queue": "heavy"},
    },

    # Auto-discover tasks
    include=["src.workers.tasks"],
)
