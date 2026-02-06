from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "munidata",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Santiago",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(bind=True, name="run_scrape_task", max_retries=2)
def run_scrape_task(self, scrape_run_id: int):
    """Execute the scraping pipeline for a given ScrapeRun."""
    from app.jobs.scrape_pipeline import execute_scrape_pipeline
    return execute_scrape_pipeline(scrape_run_id)
