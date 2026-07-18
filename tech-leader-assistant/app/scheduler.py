from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .tasks import (
    gitlab_sync_task,
    jira_sync_task,
    opensearch_ingestion_task,
    confluence_auto_link_task,
    generate_release_notes_task,
    stale_mr_reminder_task
)
import logging

logger = logging.getLogger(__name__)

# Initialize the scheduler
scheduler = AsyncIOScheduler()

def setup_scheduler():
    """Configures the APScheduler jobs."""
    # 1. GitLab sync (e.g., every 15 minutes)
    scheduler.add_job(gitlab_sync_task, 'interval', minutes=15, id="gitlab_sync")

    # 2. Jira sync (e.g., every 30 minutes)
    scheduler.add_job(jira_sync_task, 'interval', minutes=30, id="jira_sync")

    # 3. OpenSearch ingestion for RAG (e.g., daily at midnight)
    scheduler.add_job(opensearch_ingestion_task, 'cron', hour=0, minute=0, id="opensearch_ingestion")

    # 4. Confluence auto-linking (e.g., every hour)
    scheduler.add_job(confluence_auto_link_task, 'interval', hours=1, id="confluence_auto_link")

    scheduler.add_job(generate_release_notes_task, 'cron', hour=2, minute=0, id="generate_release_notes")

    scheduler.add_job(stale_mr_reminder_task, 'cron', hour=3, minute=0, id="stale_mr_reminder")

    logger.info("APScheduler jobs configured.")

def start_scheduler():
    """Starts the APScheduler."""
    if not scheduler.running:
        setup_scheduler()
        scheduler.start()
        logger.info("APScheduler started.")

def shutdown_scheduler():
    """Shuts down the APScheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler shut down.")
