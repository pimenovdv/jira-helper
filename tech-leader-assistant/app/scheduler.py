from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .tasks import (
    jira_high_complexity_warning_task,
    jira_missing_epic_reminder_task,
    gitlab_mr_approval_reminder_task,
    gitlab_sync_task,
    jira_sync_task,
    opensearch_ingestion_task,
    opensearch_stale_document_expiration_task,
    confluence_auto_link_task,
    confluence_missing_page_tag_reminder_task,
    neo4j_ghost_node_cleanup_task,
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
    jira_missing_description_reminder_task,
    gitlab_mr_missing_reviewer_notifier_task,
    jira_sprint_unassigned_task_reminder_task,
    jira_weekly_sprint_summary_task,
    gitlab_mr_title_linter_task,
    jira_missing_component_reminder_task,
    jira_missing_fixversion_reminder_task,
    gitlab_long_running_mr_reminder_task,
    jira_inactive_reporter_reminder_task,
    jira_blocked_task_alert_task,
    gitlab_mr_missing_assignee_notifier_task,
    jira_missing_labels_reminder_task,
    gitlab_stale_draft_mr_closer_task,
    jira_large_story_decomposition_reminder_task,
    jira_high_priority_out_of_sprint_reminder_task,
    gitlab_mr_description_checklist_validator_task,
    gitlab_mr_code_churn_notifier_task
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
    scheduler.add_job(opensearch_stale_document_expiration_task, 'cron', hour=1, minute=0, id="opensearch_stale_document_expiration")

    # 4. Confluence auto-linking (e.g., every hour)
    scheduler.add_job(confluence_auto_link_task, 'interval', hours=1, id="confluence_auto_link")

    # Confluence missing page tag reminder (e.g., daily)
    scheduler.add_job(confluence_missing_page_tag_reminder_task, 'cron', hour=4, minute=0, id="confluence_missing_page_tag_reminder")

    # Neo4j ghost node cleanup (e.g., daily)
    scheduler.add_job(neo4j_ghost_node_cleanup_task, 'cron', hour=5, minute=30, id="neo4j_ghost_node_cleanup")

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
    scheduler.add_job(gitlab_mr_missing_reviewer_notifier_task, 'cron', hour='*/3', minute=0, id="gitlab_mr_missing_reviewer_notifier")
    scheduler.add_job(jira_sprint_unassigned_task_reminder_task, 'cron', hour='*/4', minute=0, id="jira_sprint_unassigned_task_reminder")
    scheduler.add_job(jira_weekly_sprint_summary_task, 'cron', day_of_week='fri', hour=17, minute=0, id="jira_weekly_sprint_summary")
    scheduler.add_job(gitlab_mr_title_linter_task, 'cron', hour='*/4', minute=0, id="gitlab_mr_title_linter")
    scheduler.add_job(jira_missing_component_reminder_task, 'cron', hour='*/4', minute=15, id="jira_missing_component_reminder")
    scheduler.add_job(jira_missing_fixversion_reminder_task, 'cron', hour=10, minute=0, id="jira_missing_fixversion_reminder")
    scheduler.add_job(gitlab_long_running_mr_reminder_task, 'cron', hour=11, minute=30, id="gitlab_long_running_mr_reminder")
    scheduler.add_job(jira_inactive_reporter_reminder_task, 'cron', hour=12, minute=0, id="jira_inactive_reporter_reminder")
    scheduler.add_job(jira_blocked_task_alert_task, 'cron', hour=13, minute=0, id="jira_blocked_task_alert")
    scheduler.add_job(jira_missing_epic_reminder_task, 'cron', hour=14, minute=15, id="jira_missing_epic_reminder")
    scheduler.add_job(jira_high_complexity_warning_task, 'cron', hour=14, minute=30, id="jira_high_complexity_warning")
    scheduler.add_job(gitlab_mr_approval_reminder_task, 'cron', hour=14, minute=0, id="gitlab_mr_approval_reminder")
    scheduler.add_job(gitlab_mr_missing_assignee_notifier_task, 'cron', hour='*/3', minute=30, id="gitlab_mr_missing_assignee_notifier")
    scheduler.add_job(jira_missing_labels_reminder_task, 'cron', hour='*/4', minute=45, id="jira_missing_labels_reminder")
    scheduler.add_job(gitlab_stale_draft_mr_closer_task, 'cron', hour=3, minute=30, id="gitlab_stale_draft_mr_closer")
    scheduler.add_job(jira_large_story_decomposition_reminder_task, 'cron', hour='*/6', minute=15, id="jira_large_story_decomposition_reminder")
    scheduler.add_job(jira_high_priority_out_of_sprint_reminder_task, 'cron', hour='*/4', minute=30, id="jira_high_priority_out_of_sprint_reminder")
    scheduler.add_job(gitlab_mr_description_checklist_validator_task, 'cron', hour='*/3', minute=45, id="gitlab_mr_description_checklist_validator")
    scheduler.add_job(gitlab_mr_code_churn_notifier_task, 'cron', hour='*/4', minute=15, id="gitlab_mr_code_churn_notifier")

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
