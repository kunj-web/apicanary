from celery import Celery
import os

celery_app = Celery(
    "apicanary",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=["app.tasks.monitor_checks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "schedule-all-monitors": {
            "task": "app.tasks.monitor_checks.schedule_all_monitors",
            "schedule": 60.0, 
        },
    }
)