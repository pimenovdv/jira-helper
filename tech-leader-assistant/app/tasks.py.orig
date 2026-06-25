import re
import logging
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import OpenSearchVectorSearch

from datetime import datetime
from sqlalchemy import select
from app.clients.gitlab_client import GitLabClient
from app.clients.jira_client import JiraClient
from app.clients.confluence_client import ConfluenceClient

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

async def jira_sync_task():
    """Extracts information from Jira by configs (sprints, issues, releases)."""
    logger.info("Running Jira sync task: extracting sprint and issue information.")

    jira_client = JiraClient()
    gitlab_client = GitLabClient()

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    jira_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")

    gitlab_branches = {}
    for pid in tracked_projects:
        pid = pid.strip()
        if not pid: continue
        branches = gitlab_client.get_project_branches(pid)
        gitlab_branches[pid] = [b.name for b in branches]

    jira_issues = []
    jira_releases = []

    for j_proj in jira_projects:
        j_proj = j_proj.strip()
        if not j_proj: continue

        issues = jira_client.search_issues(f"project = {j_proj} AND (sprint in openSprints() OR updated >= -30d)")
        jira_issues.extend(issues)

        releases = jira_client.get_project_versions(j_proj)
        jira_releases.extend(releases)

    async with AsyncSessionLocal() as session:
        # Save cross-match for tasks
        for issue in jira_issues:
            task_id = issue.key
            matched_projects = []
            for pid, branches in gitlab_branches.items():
                if any(re.search(rf"\b{re.escape(task_id)}\b", b) for b in branches):
                    matched_projects.append(pid)

            event_data = {
                "task_id": task_id,
                "matched_gitlab_projects": matched_projects,
                "summary": issue.fields.summary,
                "fix_versions": [v.name for v in getattr(issue.fields, "fixVersions", [])]
            }

            existing = await session.execute(
                select(Event).where(
                    (Event.event_type == "jira_task_crossmatch") &
                    (Event.data["task_id"].astext == task_id)
                )
            )
            existing_event = existing.scalar_one_or_none()
            if not existing_event:
                event = Event(
                    event_type="jira_task_crossmatch",
                    timestamp=datetime.utcnow(),
                    data=event_data
                )
                session.add(event)
            else:
                # Update if changed
                if existing_event.data.get("matched_gitlab_projects") != matched_projects or \
                   existing_event.data.get("fix_versions") != event_data["fix_versions"] or \
                   existing_event.data.get("summary") != event_data["summary"]:
                    existing_event.data = event_data
                    existing_event.timestamp = datetime.utcnow()

        # Save cross-match for releases
        for release in jira_releases:
            release_name = release.name
            matched_projects = []
            for pid, branches in gitlab_branches.items():
                if any(re.search(rf"\b{re.escape(release_name)}\b", b) for b in branches):
                    matched_projects.append(pid)

            event_data = {
                "release_name": release_name,
                "matched_gitlab_projects": matched_projects,
                "project_key": release.projectId
            }

            existing = await session.execute(
                select(Event).where(
                    (Event.event_type == "jira_release_crossmatch") &
                    (Event.data["release_name"].astext == release_name)
                )
            )
            existing_event = existing.scalar_one_or_none()
            if not existing_event:
                event = Event(
                    event_type="jira_release_crossmatch",
                    timestamp=datetime.utcnow(),
                    data=event_data
                )
                session.add(event)
            else:
                if existing_event.data.get("matched_gitlab_projects") != matched_projects:
                    existing_event.data = event_data
                    existing_event.timestamp = datetime.utcnow()

        await session.commit()

    return "Jira sync task completed"


def opensearch_ingestion_task():
    """Daily extraction, chunking and loading into OpenSearch for RAG."""
    logger.info("Running OpenSearch ingestion task: chunking data and preparing for RAG.")

    confluence_client = ConfluenceClient()
    tracked_spaces = settings.get("CONFLUENCE_TRACKED_SPACES", "").split(",")

    # Collect pages
    confluence_pages = []
    for space in tracked_spaces:
        space = space.strip()
        if not space: continue
        try:
            # Gentle extraction: we could limit to recent updates, but for now we limit to 100 per space
            pages = confluence_client.client.get_all_pages_from_space(
                space,
                expand="body.storage",
                start=0,
                limit=100
            )
            if isinstance(pages, list):
                confluence_pages.extend(pages)
            elif isinstance(pages, dict) and "results" in pages:
                confluence_pages.extend(pages["results"])
        except Exception as e:
            logger.error(f"Error fetching pages for space {space}: {e}")

    if not confluence_pages:
        logger.info("No pages found to ingest.")
        return "OpenSearch ingestion task completed (no pages)"

    # Clean HTML and prepare documents
    documents = []
    metadatas = []
    for page in confluence_pages:
        page_id = str(page.get("id"))
        title = page.get("title", "")

        # Extract body
        body = ""
        if "body" in page and "storage" in page["body"]:
            html_content = page["body"]["storage"].get("value", "")
            soup = BeautifulSoup(html_content, "html.parser")
            body = soup.get_text(separator=" ", strip=True)

        if not body:
            continue

        documents.append(f"Title: {title}\n\n{body}")

        metadatas.append({"page_id": page_id, "title": title, "source": "confluence"})

    if not documents:
        return "OpenSearch ingestion task completed (no content)"

    # Chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        length_function=len,
    )

    docs = text_splitter.create_documents(documents, metadatas=metadatas)

    # Embeddings
    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping embedding generation.")
        return "OpenSearch ingestion task skipped (no OpenAI API key)"

    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)

    # OpenSearch ingestion
    os_url = settings.get("OPENSEARCH_URL")
    os_user = settings.get("OPENSEARCH_USER")
    os_password = settings.get("OPENSEARCH_PASSWORD")
    verify_certs = settings.get("OPENSEARCH_VERIFY_CERTS", default=True)

    try:
        OpenSearchVectorSearch.from_documents(
            docs,
            embeddings,
            opensearch_url=os_url,
            http_auth=(os_user, os_password),
            use_ssl=True,
            verify_certs=verify_certs,
            ssl_assert_hostname=verify_certs,
            ssl_show_warn=not verify_certs,
            index_name="confluence-rag-index"
        )
        logger.info(f"Successfully ingested {len(docs)} chunks into OpenSearch.")
    except Exception as e:
        logger.error(f"Error during OpenSearch ingestion: {e}")
        return "OpenSearch ingestion task failed"

    return "OpenSearch ingestion task completed"
async def confluence_auto_link_task():
    """Automatically linking Confluence pages to Git projects based on titles."""
    logger.info("Running Confluence auto-linking task: linking pages to Git projects.")

    gitlab_client = GitLabClient()
    confluence_client = ConfluenceClient()

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_spaces = settings.get("CONFLUENCE_TRACKED_SPACES", "").split(",")

    project_names = {}
    for pid in tracked_projects:
        pid = pid.strip()
        if not pid: continue
        project = gitlab_client.get_project(pid)
        if project:
            project_names[pid] = project.name

    confluence_pages = []
    for space in tracked_spaces:
        space = space.strip()
        if not space: continue
        try:
            pages = confluence_client.client.get_all_pages_from_space(space, expand="space", start=0, limit=100)
            if isinstance(pages, list):
                confluence_pages.extend(pages)
            elif isinstance(pages, dict) and "results" in pages:
                confluence_pages.extend(pages["results"])
        except Exception as e:
            logger.error(f"Error fetching pages for space {space}: {e}")

    async with AsyncSessionLocal() as session:
        for page in confluence_pages:
            page_id = str(page.get("id"))
            page_title = page.get("title", "")

            auto_linked_projects = []
            for pid, pname in project_names.items():
                if pname.lower() in page_title.lower():
                    auto_linked_projects.append(pid)

            existing = await session.execute(
                select(Event).where(
                    (Event.event_type == "confluence_project_link") &
                    (Event.data["page_id"].astext == page_id)
                )
            )
            existing_event = existing.scalar_one_or_none()

            if not auto_linked_projects and not existing_event:
                continue

            if not existing_event:
                event_data = {
                    "page_id": page_id,
                    "page_title": page_title,
                    "auto_linked_projects": auto_linked_projects,
                    "manual_linked_projects": [],
                    "manual_unlinked_projects": []
                }
                event = Event(
                    event_type="confluence_project_link",
                    timestamp=datetime.utcnow(),
                    data=event_data
                )
                session.add(event)
            else:
                current_data = existing_event.data.copy()
                if current_data.get("auto_linked_projects") != auto_linked_projects or current_data.get("page_title") != page_title:
                    current_data["auto_linked_projects"] = auto_linked_projects
                    current_data["page_title"] = page_title
                    existing_event.data = current_data
                    existing_event.timestamp = datetime.utcnow()

        await session.commit()

    return "Confluence auto-linking task completed"
