from celery import Celery

from app.core.config import get_settings


settings = get_settings()
celery_app = Celery("live_pulse", broker=settings.redis_url, backend=settings.redis_url, include=["app.tasks"])
celery_app.conf.task_track_started = True
celery_app.conf.beat_schedule = {
    "run-scheduled-agents-every-5-minutes": {
        "task": "app.tasks.run_scheduled_agents",
        "schedule": 300.0,
    }
}
celery_app.conf.timezone = "Europe/Paris"
