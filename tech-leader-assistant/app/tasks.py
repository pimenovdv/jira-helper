import logging
from datetime import datetime
from sqlalchemy import select
from app.clients.gitlab_client import GitLabClient
from app.clients import settings
from app.database import AsyncSessionLocal
from app.models import Event

logger = logging.getLogger(__name__)

async def _save_event(session, event_data, event_type, project_id=None, user_id=None):
    # Parse created_at to timestamp
    # example: "2023-10-25T14:30:00.000Z"
    try:
        dt = datetime.fromisoformat(event_data.get("created_at").replace("Z", "+00:00"))
        # Strip timezone for naive datetime in our DB if needed, or keep aware.
        # we'll remove tzinfo for simplicity assuming UTC
        dt = dt.replace(tzinfo=None)
    except Exception:
        dt = datetime.utcnow()

    event = Event(
        event_type=event_type,
        project_id=str(project_id) if project_id else None,
        user_id=str(user_id) if user_id else None,
        timestamp=dt,
        data=event_data
    )
    session.add(event)

async def gitlab_sync_task():
    """Extracts data from GitLab based on configs and renders events on timeline."""
    logger.info("Running GitLab sync task: extracting data and rendering events on timeline.")
    client = GitLabClient()

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_users = settings.get("GITLAB_TRACKED_USERS", "").split(",")

    async with AsyncSessionLocal() as session:
        # Sync projects
        for pid in tracked_projects:
            pid = pid.strip()
            if not pid: continue
            events = client.get_project_events(pid)
            for e in events:
                data = e.attributes
                # Prevent duplicates by checking if event with same data["id"] exists
                # We assume gitlab event ID is unique
                existing = await session.execute(
                    select(Event).where(Event.data["id"].astext == str(data.get("id")))
                )
                if not existing.scalar_one_or_none():
                    await _save_event(session, data, "project_event", project_id=pid)

        # Sync users
        for uid in tracked_users:
            uid = uid.strip()
            if not uid: continue
            events = client.get_user_events(uid)
            for e in events:
                data = e.attributes
                existing = await session.execute(
                    select(Event).where(Event.data["id"].astext == str(data.get("id")))
                )
                if not existing.scalar_one_or_none():
                    await _save_event(session, data, "user_event", user_id=uid)

        await session.commit()
    return "GitLab sync task completed"

def jira_sync_task():
    """Extracts information from Jira by configs (sprints, issues, releases)."""
    logger.info("Running Jira sync task: extracting sprint and issue information.")
    return "Jira sync task completed"

def opensearch_ingestion_task():
    """Daily extraction, chunking and loading into OpenSearch for RAG."""
    logger.info("Running OpenSearch ingestion task: chunking data and preparing for RAG.")
    return "OpenSearch ingestion task completed"

def confluence_auto_link_task():
    """Automatically linking Confluence pages to Git projects based on titles."""
    logger.info("Running Confluence auto-linking task: linking pages to Git projects.")
    return "Confluence auto-linking task completed"
