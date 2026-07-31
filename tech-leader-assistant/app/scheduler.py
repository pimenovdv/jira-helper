from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .tasks import (
    gitlab_sync_task,
    jira_sync_task,
    opensearch_ingestion_task,
    confluence_auto_link_task,
    generate_release_notes_task,
    stale_mr_reminder_task,
    stale_jira_task_reminder_task,
    gitlab_mr_size_labeler_task,
    gitlab_draft_labeler_task,
    gitlab_merged_branch_cleanup_task,
    gitlab_mr_jira_validator_task,
    gitlab_mr_conflict_notifier_task,
    gitlab_empty_mr_description_notifier_task,
    jira_missing_estimation_reminder_task,
    gitlab_unresolved_threads_reminder_task,
    gitlab_mr_cicd_failure_notifier_task,
    jira_missing_acceptance_criteria_reminder_task,
    gitlab_mr_too_many_comments_notifier_task,
    jira_overdue_task_reminder_task,
    gitlab_mr_missing_tests_notifier_task,
    jira_missing_description_reminder_task
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

    scheduler.add_job(stale_jira_task_reminder_task, 'cron', hour=4, minute=0, id="stale_jira_task_reminder")

    scheduler.add_job(gitlab_mr_size_labeler_task, 'cron', hour='*/2', minute=0, id="gitlab_mr_size_labeler")

    scheduler.add_job(gitlab_draft_labeler_task, 'cron', hour='*', minute=30, id="gitlab_draft_labeler")

    scheduler.add_job(gitlab_merged_branch_cleanup_task, 'cron', hour=5, minute=0, id="gitlab_merged_branch_cleanup")

    scheduler.add_job(gitlab_mr_jira_validator_task, 'cron', hour='*', minute=45, id="gitlab_mr_jira_validator")

    scheduler.add_job(gitlab_mr_conflict_notifier_task, 'interval', hours=1, id="gitlab_mr_conflict_notifier")

    scheduler.add_job(gitlab_empty_mr_description_notifier_task, 'cron', hour='*/6', minute=0, id="gitlab_empty_mr_description_notifier")

    scheduler.add_job(jira_missing_estimation_reminder_task, 'cron', hour=7, minute=0, id="jira_missing_estimation_reminder")

    scheduler.add_job(gitlab_unresolved_threads_reminder_task, 'cron', hour='*/6', minute=30, id="gitlab_unresolved_threads_reminder")

    scheduler.add_job(gitlab_mr_cicd_failure_notifier_task, 'interval', minutes=30, id="gitlab_mr_cicd_failure_notifier")

    scheduler.add_job(jira_missing_acceptance_criteria_reminder_task, 'cron', hour=8, minute=0, id="jira_missing_acceptance_criteria_reminder")

    scheduler.add_job(gitlab_mr_too_many_comments_notifier_task, 'cron', hour='*/6', minute=45, id="gitlab_mr_too_many_comments_notifier")
    scheduler.add_job(jira_overdue_task_reminder_task, 'cron', hour=9, minute=0, id="jira_overdue_task_reminder")
    scheduler.add_job(gitlab_mr_missing_tests_notifier_task, 'cron', hour='*/4', minute=15, id="gitlab_mr_missing_tests_notifier")
    scheduler.add_job(jira_missing_description_reminder_task, 'cron', hour='*/4', minute=30, id="jira_missing_description_reminder")

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
