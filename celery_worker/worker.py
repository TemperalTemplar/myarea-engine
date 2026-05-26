"""
MyArea Celery Worker
Handles: energy/stamina regen, property income, daily resets, hospital release.
"""

from celery import Celery
from celery.schedules import crontab
import os

# Create Celery app (app context injected by ContextTask in factory)
worker = Celery("myarea")
worker.conf.update(
    broker_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    result_backend=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# ─── Periodic task schedule ──────────────────────────────────
worker.conf.beat_schedule = {
    # Energy regeneration — every 5 minutes
    "regen-energy": {
        "task": "celery_worker.tasks.regen_energy",
        "schedule": 300.0,
    },
    # Stamina regeneration — every 3 minutes
    "regen-stamina": {
        "task": "celery_worker.tasks.regen_stamina",
        "schedule": 180.0,
    },
    # Property income tick — every 15 minutes (marks dirty, player collects)
    "property-income-tick": {
        "task": "celery_worker.tasks.property_income_tick",
        "schedule": 900.0,
    },
    # Release players from hospital — every minute
    "hospital-release": {
        "task": "celery_worker.tasks.hospital_release",
        "schedule": 60.0,
    },
    # Release players from jail — every minute
    "jail-release": {
        "task": "celery_worker.tasks.jail_release",
        "schedule": 60.0,
    },
    # Daily reset — midnight UTC
    "daily-reset": {
        "task": "celery_worker.tasks.daily_reset",
        "schedule": crontab(hour=0, minute=0),
    },
    # Leaderboard cache refresh — every 10 minutes
    "refresh-leaderboard": {
        "task": "celery_worker.tasks.refresh_leaderboard_cache",
        "schedule": 600.0,
    },
}

# Import tasks so Celery discovers them
from celery_worker import tasks  # noqa: F401, E402
