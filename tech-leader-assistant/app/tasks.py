import re
import logging
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import OpenSearchVectorSearch

from datetime import datetime
from sqlalchemy import select
from app.clients.gitlab_client import GitLabClient
from app.clients.jira_client import JiraClient
from app.clients.confluence_client import ConfluenceClient
from app.clients.opensearch_client import OpenSearchClient
from app.clients.neo4j_client import Neo4jClient

global GitLabClient
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
    neo4j_client = Neo4jClient()

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    jira_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")

    gitlab_branches = {}
    for pid in tracked_projects:
        pid = pid.strip()
        if not pid: continue
        branches = gitlab_client.get_project_branches(pid)
        gitlab_branches[pid] = [b.name for b in branches if hasattr(b, "name")]

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

            for pid in matched_projects:
                neo4j_client.link_task_to_project(task_id, pid)

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

            # Tasks associated with this release
            release_tasks = []
            for issue in jira_issues:
                fix_versions = [v.name for v in getattr(issue.fields, "fixVersions", [])]
                if release_name in fix_versions:
                    release_tasks.append(issue)

            task_statuses = {}
            for pid, branches in gitlab_branches.items():
                if any(re.search(rf"\b{re.escape(release_name)}\b", b) for b in branches):
                    matched_projects.append(pid)

                # For readiness check, we check if feature branches are merged into release branch
                release_branch = next((b for b in branches if re.search(rf"\b{re.escape(release_name)}\b", b)), None)
                if release_branch:
                    for task in release_tasks:
                        task_id = task.key
                        # Find task branches
                        task_branch = next((b for b in branches if re.search(rf"{re.escape(task_id)}", b)), None)
                        if task_branch:
                            is_merged = gitlab_client.is_branch_merged(pid, task_branch, release_branch)
                            if task_id not in task_statuses:
                                task_statuses[task_id] = []
                            task_statuses[task_id].append({
                                "project_id": pid,
                                "branch": task_branch,
                                "merged": is_merged
                            })

            all_tasks_ready = True
            for task in release_tasks:
                task_id = task.key
                # If a task has no branches matched, we might consider it not ready, or maybe we just ignore.
                # The requirements say: check if all feature branches have been merged
                if task_id in task_statuses:
                    for branch_status in task_statuses[task_id]:
                        if not branch_status["merged"]:
                            all_tasks_ready = False
                            break
                else:
                    # If task has no branch, it's not ready to merge feature branches
                    all_tasks_ready = False
                    pass

            for pid in matched_projects:
                neo4j_client.link_release_to_project(release_name, pid)

            event_data = {
                "release_name": release_name,
                "matched_gitlab_projects": matched_projects,
                "project_key": release.projectId,
                "ready_for_release": all_tasks_ready,
                "tasks": [{"task_id": t.key, "summary": t.fields.summary, "statuses": task_statuses.get(t.key, [])} for t in release_tasks]
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
                if existing_event.data.get("matched_gitlab_projects") != matched_projects or \
                   existing_event.data.get("ready_for_release") != all_tasks_ready or \
                   existing_event.data.get("tasks") != event_data["tasks"]:
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

def opensearch_stale_document_expiration_task():
    """Prunes old, inactive wiki chunks from RAG index if the page no longer exists or is untracked."""
    logger.info("Running OpenSearch Stale Document Expiration task.")

    confluence_client = ConfluenceClient()
    tracked_spaces = settings.get("CONFLUENCE_TRACKED_SPACES", "").split(",")

    active_page_ids = []
    for space in tracked_spaces:
        space = space.strip()
        if not space: continue
        try:
            pages = confluence_client.client.get_all_pages_from_space(
                space,
                start=0,
                limit=500
            )
            if isinstance(pages, list):
                active_page_ids.extend([str(p.get("id")) for p in pages])
            elif isinstance(pages, dict) and "results" in pages:
                active_page_ids.extend([str(p.get("id")) for p in pages["results"]])
        except Exception as e:
            logger.error(f"Error fetching pages for space {space} in stale document expiration: {e}")

    if not active_page_ids:
        logger.info("No active pages found or tracked spaces empty. Skipping stale document pruning.")
        return "Stale document expiration skipped (no active pages)"

    os_client = OpenSearchClient()

    query = {
        "query": {
            "bool": {
                "must_not": [
                    {
                        "terms": {
                            "metadata.page_id.keyword": active_page_ids
                        }
                    }
                ],
                "filter": [
                    {
                        "term": {
                            "metadata.source.keyword": "confluence"
                        }
                    }
                ]
            }
        }
    }

    try:
        response = os_client.client.delete_by_query(
            index="confluence-rag-index",
            body=query,
            conflicts="proceed"
        )
        deleted = response.get("deleted", 0)
        logger.info(f"Successfully pruned {deleted} stale documents from OpenSearch.")
    except Exception as e:
        logger.error(f"Error during OpenSearch stale document expiration: {e}")
        return "Stale document expiration failed"

    return "Stale document expiration completed"

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



async def confluence_missing_page_tag_reminder_task():
    """
    Notifies if a Confluence page is missing required tags/labels.
    Uses the LLM to generate a polite reminder in Russian and posts it as a comment.
    """
    import logging
    from langchain_core.messages import HumanMessage

    logger = logging.getLogger(__name__)
    logger.info("Starting Confluence missing page tag reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping Confluence missing page tag reminder.")
        return "Confluence missing page tag reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    confluence_client = ConfluenceClient()

    tracked_spaces = settings.get("CONFLUENCE_TRACKED_SPACES", "").split(",")
    tracked_spaces = [s.strip() for s in tracked_spaces if s.strip()]

    required_tags_str = settings.get("CONFLUENCE_REQUIRED_TAGS", "")
    if not required_tags_str:
        logger.info("No CONFLUENCE_REQUIRED_TAGS configured. Skipping task.")
        return "Confluence missing page tag reminder task skipped (no required tags configured)"

    required_tags = [t.strip().lower() for t in required_tags_str.split(",") if t.strip()]

    marker = "<!-- AUTO_GENERATED_CONFLUENCE_TAG_REMINDER -->"

    for space in tracked_spaces:
        try:
            pages_response = confluence_client.client.get_all_pages_from_space(space, start=0, limit=100)
            pages = []
            if isinstance(pages_response, list):
                pages = pages_response
            elif isinstance(pages_response, dict) and "results" in pages_response:
                pages = pages_response["results"]

            for page in pages:
                page_id = page["id"]
                title = page.get("title", f"Page {page_id}")

                # Fetch labels
                labels_response = confluence_client.client.get_page_labels(page_id)
                page_labels = []
                if isinstance(labels_response, dict) and "results" in labels_response:
                    page_labels = [l.get("name", "").lower() for l in labels_response["results"]]

                missing_tags = [t for t in required_tags if t not in page_labels]

                if missing_tags:
                    # Check if reminder already exists
                    comments_response = confluence_client.client.get_page_comments(page_id, expand="body.storage")
                    comments = []
                    if isinstance(comments_response, dict) and "results" in comments_response:
                        comments = comments_response["results"]

                    already_reminded = False
                    for comment in comments:
                        body = comment.get("body", {}).get("storage", {}).get("value", "")
                        if marker in body:
                            already_reminded = True
                            break

                    if not already_reminded:
                        missing_tags_str = ", ".join(missing_tags)
                        logger.info(f"Page '{title}' ({page_id}) is missing tags: {missing_tags_str}. Generating reminder.")
                        prompt = (
                            f"Сгенерируй короткое и вежливое напоминание (в 1-2 предложениях) автору страницы в Confluence '{title}', "
                            f"о том, что на странице не хватает обязательных тегов: {missing_tags_str}. "
                            f"Попроси добавить их. "
                            f"Верни только текст напоминания, без кавычек и дополнительных пояснений."
                        )
                        response = await llm.ainvoke([HumanMessage(content=prompt)])
                        comment_body = f"{response.content}<br/>{marker}"
                        try:
                            confluence_client.client.add_comment(page_id, comment_body)
                            logger.info(f"Posted reminder to page '{title}' ({page_id}).")
                        except Exception as e:
                            logger.error(f"Failed to post reminder to page '{title}': {e}")

        except Exception as e:
            logger.error(f"Error processing space {space}: {e}")

    return "Confluence missing page tag reminder task completed."

async def neo4j_ghost_node_cleanup_task():
    """Removes Jira/GitLab nodes in graph DB that no longer exist in sources."""
    logger.info("Running Neo4j ghost node cleanup task.")

    jira_client = JiraClient()
    neo4j_client = Neo4jClient()

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    gitlab_projects = [pid.strip() for pid in tracked_projects if pid.strip()]

    jira_projects_setting = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    jira_projects = [j_proj.strip() for j_proj in jira_projects_setting if j_proj.strip()]

    active_tasks = []
    active_releases = []

    for j_proj in jira_projects:
        issues = jira_client.search_issues(f"project = {j_proj} AND (sprint in openSprints() OR updated >= -30d)")
        active_tasks.extend([issue.key for issue in issues])

        releases = jira_client.get_project_versions(j_proj)
        active_releases.extend([getattr(release, "name", release) for release in releases])

    all_active_projects = gitlab_projects + jira_projects

    # Add ghost node cleanup call
    neo4j_client.cleanup_ghost_nodes(active_tasks, active_releases, all_active_projects)

    logger.info("Neo4j ghost node cleanup task completed.")
    return "Neo4j ghost node cleanup task completed."

def generate_release_notes_task():
    """Fetches Jira releases, gets context from OpenSearch, drafts release notes, and publishes to Confluence."""
    logger.info("Running automated release notes generator task.")

    jira_client = JiraClient()
    confluence_client = ConfluenceClient()

    jira_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_spaces = settings.get("CONFLUENCE_TRACKED_SPACES", "").split(",")

    if not tracked_spaces or not tracked_spaces[0]:
        logger.warning("No confluence spaces tracked for release notes.")
        return "Release notes task completed (no spaces)"

    space = tracked_spaces[0].strip()

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping release notes generation.")
        return "Release notes task skipped (no OpenAI API key)"

    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)

    os_url = settings.get("OPENSEARCH_URL")
    os_user = settings.get("OPENSEARCH_USER")
    os_password = settings.get("OPENSEARCH_PASSWORD")
    verify_certs = settings.get("OPENSEARCH_VERIFY_CERTS", default=True)

    vectorstore = OpenSearchVectorSearch(
        opensearch_url=os_url,
        index_name="confluence-rag-index",
        embedding_function=embeddings,
        http_auth=(os_user, os_password),
        use_ssl=True,
        verify_certs=verify_certs,
        ssl_assert_hostname=verify_certs,
        ssl_show_warn=not verify_certs,
    )
    retriever = vectorstore.as_retriever()

    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, openai_api_key=openai_api_key)

    for j_proj in jira_projects:
        j_proj = j_proj.strip()
        if not j_proj: continue

        releases = jira_client.get_project_versions(j_proj)
        if not releases:
            continue

        issues = jira_client.search_issues(f"project={j_proj}")

        for release in releases:
            release_name = release.name

            # Find tasks for this release
            release_tasks = []
            for issue in issues:
                fix_versions = [v.name for v in getattr(issue.fields, "fixVersions", [])]
                if release_name in fix_versions:
                    release_tasks.append(issue)

            if not release_tasks:
                continue

            # Gather summaries and context
            task_summaries = []
            all_contexts = []
            for task in release_tasks:
                summary = getattr(task.fields, "summary", "")
                task_summaries.append(f"- {task.key}: {summary}")

                # Fetch context for this task
                docs = retriever.invoke(summary)
                all_contexts.extend([doc.page_content for doc in docs])

            tasks_text = "\n".join(task_summaries)

            # Deduplicate context somewhat
            context_text = "\n\n".join(list(set(all_contexts))[:10]) # limit context to prevent token overflow

            prompt = ChatPromptTemplate.from_template(
                "Ты — полезный ассистент технического лидера. Твоя задача — составить черновик release notes (в формате HTML) "
                "на основе списка задач из Jira и контекста из Confluence.\n\n"
                "Задачи в релизе:\n{tasks}\n\n"
                "Контекст из документации:\n{context}\n\n"
                "Сгенерируй только HTML-код (без тегов markdown, только HTML, который можно вставить в body страницы). "
                "Используй русский язык."
            )

            chain = prompt | llm

            try:
                response = chain.invoke({"tasks": tasks_text, "context": context_text})
                html_content = response.content

                # Clean up response if LLM added markdown tags
                if html_content.startswith("```html"):
                    html_content = html_content[7:]
                if html_content.endswith("```"):
                    html_content = html_content[:-3]

                # Create page in Confluence
                title = f"Release Notes {release_name}"
                confluence_client.client.create_page(
                    space=space,
                    title=title,
                    body=html_content,
                    parent_id=None
                )
                logger.info(f"Published release notes for {release_name} to space {space}.")
            except Exception as e:
                logger.error(f"Failed to generate or publish release notes for {release_name}: {e}")

    return "Release notes task completed"


async def mr_summarization_task():
    """
    Iterates over tracked GitLab projects and fetches open Merge Requests.
    Generates a summary of changes and suggests test recommendations via LLM,
    and posts the output as a note on the GitLab MR (if not already posted).
    """
    logger.info("Starting automated MR summarization task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping MR summarization.")
        return "MR summarization task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    summary_marker = "<!-- AUTO_GENERATED_MR_SUMMARY -->"

    for project_id in tracked_projects:
        try:
            gitlab_client = GitLabClient()
            mrs = gitlab_client.get_project_merge_requests(project_id, state="opened")
            for mr in mrs:
                try:
                    notes = mr.notes.list(all=True)
                    already_summarized = any(summary_marker in note.body for note in notes)
                    if already_summarized:
                        continue

                    changes = gitlab_client.get_merge_request_changes(project_id, mr.iid)
                    diffs = [change.get('diff', '') for change in changes.get('changes', []) if change.get('diff')]

                    if not diffs:
                        continue

                    diff_text = "\n".join(diffs)

                    # Prevent sending too large context to LLM
                    if len(diff_text) > 10000:
                        diff_text = diff_text[:10000] + "\n...[diff truncated]"

                    # HumanMessage imported globally
                    prompt = (
                        f"Ты - технический помощник. Пожалуйста, проанализируй следующий diff-файл Merge Request "
                        f"и сгенерируй:\n1. Краткое резюме изменений.\n2. Рекомендации по написанию тестов.\n\n"
                        f"Diff:\n{diff_text}"
                    )

                    response = llm.invoke([HumanMessage(content=prompt)])

                    note_body = f"{summary_marker}\n\n{response.content}"
                    gitlab_client.create_mr_note(project_id, mr.iid, note_body)
                except Exception as e:
                    logger.error(f"Error summarizing MR {mr.iid} in project {project_id}: {e}")
        except Exception as e:
            logger.error(f"Error processing MR summarization for project {project_id}: {e}")


async def automated_code_review_task():
    """
    Task to review code changes in all open MRs across tracked repositories,
    evaluating them against coding guidelines stored in OpenSearch,
    and submitting automated feedback via MR notes in GitLab.
    """
    logger.info("Starting automated code review task...")
    # from app.clients.gitlab_client import GitLabClient (moved to global)
    from app.clients.opensearch_client import OpenSearchClient

    # ChatOpenAI imported globally
    from langchain_core.messages import HumanMessage

    gitlab_client = GitLabClient()
    opensearch_client = OpenSearchClient()

    # Create the LLM instance
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    for project_id in tracked_projects:
        try:
            mrs = gitlab_client.get_project_merge_requests(project_id, state="opened")
            for mr in mrs:
                # Get changes
                changes = gitlab_client.get_merge_request_changes(project_id, mr.iid)
                diffs = [change.get('diff', '') for change in changes.get('changes', []) if change.get('diff')]

                if not diffs:
                    continue

                diff_text = "\n".join(diffs)

                # Query OpenSearch for coding guidelines
                query = {
                    "query": {
                        "match": {
                            "content": "coding guidelines standards"
                        }
                    }
                }
                os_results = opensearch_client.search(index_name="confluence", body=query, size=3)
                guidelines = "\n".join([hit['_source'].get('content', '') for hit in os_results.get('hits', {}).get('hits', [])])

                # Formulate the prompt
                prompt = f"Вы - эксперт-рецензент кода. Пожалуйста, проанализируйте следующий diff-файл и дайте отзыв. Убедитесь, что код соответствует нашим стандартам кодирования, если они применимы.\n\nDiff:\n{diff_text}\n\nСтандарты кодирования:\n{guidelines}"

                # Get LLM review
                review_response = llm.invoke([HumanMessage(content=prompt)])

                # Post review as a note on the MR
                gitlab_client.create_mr_note(project_id, mr.iid, review_response.content)
        except Exception as e:
            logger.error(f"Error in automated code review for project {project_id}: {e}")

async def stale_mr_reminder_task():
    """
    Iterates over tracked GitLab projects and fetches open Merge Requests.
    Checks if an MR has been inactive for more than 7 days.
    If so, and if no automated reminder has been sent yet, uses the LLM
    to generate a polite nudge (in Russian) to encourage review or closure,
    and posts it as a note on the GitLab MR.
    """
    # from app.clients.gitlab_client import GitLabClient (moved to global)

    # ChatOpenAI imported globally
    # HumanMessage imported globally
    from datetime import datetime, timezone
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Starting automated stale MR reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping stale MR reminder.")
        return "Stale MR reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_STALE_MR_REMINDER -->"
    now = datetime.now(timezone.utc)

    for project_id in tracked_projects:
        try:
            gitlab_client = GitLabClient()
            mrs = gitlab_client.get_project_merge_requests(project_id, state="opened")
            for mr in mrs:
                try:
                    # Check updated_at
                    # GitLab's updated_at format is ISO 8601, e.g. "2023-01-01T12:00:00.000Z"
                    updated_at_str = mr.updated_at
                    # Replace Z with +00:00 for fromisoformat compatibility in python < 3.11
                    if updated_at_str.endswith('Z'):
                        updated_at_str = updated_at_str[:-1] + '+00:00'
                    updated_at = datetime.fromisoformat(updated_at_str)

                    days_inactive = (now - updated_at).days
                    if days_inactive <= 7:
                        continue

                    notes = mr.notes.list(all=True)
                    already_reminded = any(reminder_marker in note.body for note in notes)
                    if already_reminded:
                        continue

                    prompt = (
                        f"Ты - вежливый технический помощник. Пожалуйста, напиши дружелюбное напоминание для команды "
                        f"о Merge Request, который не обновлялся уже {days_inactive} дней. "
                        f"Заголовок MR: '{mr.title}'. "
                        f"Предложи команде посмотреть MR, провести ревью или закрыть его, если он больше не актуален. "
                        f"Используй русский язык."
                    )

                    response = llm.invoke([HumanMessage(content=prompt)])

                    note_body = f"{reminder_marker}\n\n{response.content}"
                    gitlab_client.create_mr_note(project_id, mr.iid, note_body)
                except Exception as e:
                    logger.error(f"Error checking stale MR {mr.iid} in project {project_id}: {e}")
        except Exception as e:
            logger.error(f"Error processing stale MR reminder for project {project_id}: {e}")


async def stale_jira_task_reminder_task():
    """
    Iterates over tracked Jira projects and fetches issues in progress or review.
    Checks if an issue hasn't been updated for 7+ days.
    If so, generates a polite nudge (in Russian) via LLM to encourage an update,
    and posts it as a comment on the Jira issue if not already posted.
    """

    from datetime import datetime, timezone
    import logging
    import dateutil.parser

    logger = logging.getLogger(__name__)
    logger.info("Starting automated stale Jira task reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping stale Jira task reminder.")
        return "Stale Jira task reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)

    jira_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    jira_projects = [p.strip() for p in jira_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_STALE_JIRA_TASK_REMINDER -->"
    now = datetime.now(timezone.utc)
    jira_client = JiraClient()

    for project_key in jira_projects:
        try:
            jql = f'project = "{project_key}" AND statusCategory IN ("In Progress") AND updated <= -7d'
            issues = jira_client.search_issues(jql)
            for issue in issues:
                try:
                    updated_at_str = issue.fields.updated
                    updated_at = dateutil.parser.isoparse(updated_at_str)
                    days_inactive = (now - updated_at).days

                    if days_inactive <= 7:
                        continue

                    comments = jira_client.get_comments(issue.key)
                    already_reminded = False
                    for comment in comments:
                        if reminder_marker in getattr(comment, 'body', ''):
                            already_reminded = True
                            break

                    if already_reminded:
                        continue

                    summary = getattr(issue.fields, "summary", "")

                    prompt = (
                        f"Ты - вежливый технический помощник. Пожалуйста, напиши дружелюбное напоминание для команды "
                        f"о задаче Jira, которая находится в работе, но не обновлялась уже {days_inactive} дней. "
                        f"Заголовок задачи: '{summary}'. "
                        f"Предложи команде актуализировать статус, добавить комментарий о прогрессе или закрыть задачу, если она больше не актуальна. "
                        f"Используй русский язык."
                    )

                    response = llm.invoke([HumanMessage(content=prompt)])
                    note_body = f"{reminder_marker}\n\n{response.content}"

                    jira_client.add_comment(issue.key, note_body)
                    logger.info(f"Posted stale reminder on Jira task {issue.key}")

                except Exception as e:
                    logger.error(f"Error checking stale Jira task {issue.key}: {e}")
        except Exception as e:
            logger.error(f"Error processing stale Jira task reminder for project {project_key}: {e}")

    return "Stale Jira task reminder task completed"

async def gitlab_mr_size_labeler_task():
    """
    Iterates over tracked GitLab projects and fetches open Merge Requests.
    Checks if an MR already has a size label. If not, calculates the diff size
    and assigns a size label.
    """


    logger.info("Starting GitLab MR size labeler task...")

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    gitlab_client = GitLabClient()

    for project_id in tracked_projects:
        try:
            mrs = gitlab_client.get_project_merge_requests(project_id, state="opened")
            for mr in mrs:
                try:
                    # Check if MR already has a size label
                    has_size_label = any(label.startswith("size:") for label in mr.labels)
                    if has_size_label:
                        continue

                    changes = gitlab_client.get_merge_request_changes(project_id, mr.iid)
                    if not changes:
                        continue

                    total_changes = 0
                    for change in changes.get("changes", []):
                        diff = change.get("diff", "")
                        for line in diff.split("\n"):
                            if line.startswith("+") and not line.startswith("+++"):
                                total_changes += 1
                            elif line.startswith("-") and not line.startswith("---"):
                                total_changes += 1

                    # Assign size based on lines changed
                    if total_changes < 10:
                        size = "XS"
                    elif total_changes < 50:
                        size = "S"
                    elif total_changes < 250:
                        size = "M"
                    elif total_changes < 1000:
                        size = "L"
                    else:
                        size = "XL"

                    new_label = f"size: {size}"
                    new_labels = mr.labels + [new_label]

                    gitlab_client.update_mr_labels(project_id, mr.iid, new_labels)
                    logger.info(f"Assigned label {new_label} to MR {mr.iid} in project {project_id}")

                except Exception as e:
                    logger.error(f"Error processing MR {mr.iid} in project {project_id} for size labeler: {e}")
        except Exception as e:
            logger.error(f"Error processing MR size labeler for project {project_id}: {e}")


async def gitlab_draft_labeler_task():
    """
    Iterates over tracked GitLab projects and fetches open Merge Requests.
    Checks if an MR title starts with 'Draft:' or 'WIP:' and assigns a 'status: draft' label.
    If it does not start with these prefixes but has the label, it removes the label.
    """


    logger.info("Starting GitLab MR draft labeler task...")

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    gitlab_client = GitLabClient()

    for project_id in tracked_projects:
        try:
            mrs = gitlab_client.get_project_merge_requests(project_id, state="opened")
            for mr in mrs:
                try:
                    title = getattr(mr, "title", "")
                    labels = list(getattr(mr, "labels", []))

                    is_draft_title = title.startswith("Draft:") or title.startswith("WIP:")
                    has_draft_label = "status: draft" in labels

                    if is_draft_title and not has_draft_label:
                        labels.append("status: draft")
                        gitlab_client.update_mr_labels(project_id, mr.iid, labels)
                        logger.info(f"Assigned 'status: draft' label to MR {mr.iid} in project {project_id}")
                    elif not is_draft_title and has_draft_label:
                        labels.remove("status: draft")
                        gitlab_client.update_mr_labels(project_id, mr.iid, labels)
                        logger.info(f"Removed 'status: draft' label from MR {mr.iid} in project {project_id}")

                except Exception as e:
                    logger.error(f"Error processing MR {mr.iid} in project {project_id} for draft labeler: {e}")
        except Exception as e:
            logger.error(f"Error processing MR draft labeler for project {project_id}: {e}")


async def gitlab_merged_branch_cleanup_task():
    """
    Iterates over tracked GitLab projects and fetches branches.
    Deletes branches that are already merged, excluding protected and default branches.
    """
    logger.info("Starting GitLab merged branch cleanup task...")

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    gitlab_client = GitLabClient()

    for project_id in tracked_projects:
        try:
            branches = gitlab_client.get_project_branches(project_id)
            for branch in branches:
                try:
                    name = getattr(branch, "name", "")
                    is_merged = getattr(branch, "merged", False)
                    is_protected = getattr(branch, "protected", False)
                    is_default = getattr(branch, "default", False)

                    if is_merged and not is_protected and not is_default:
                        success = gitlab_client.delete_branch(project_id, name)
                        if success:
                            logger.info(f"Deleted merged branch '{name}' in project {project_id}")
                        else:
                            logger.warning(f"Failed to delete merged branch '{name}' in project {project_id}")
                except Exception as e:
                    logger.error(f"Error processing branch {getattr(branch, 'name', 'unknown')} in project {project_id} for cleanup: {e}")
        except Exception as e:
            logger.error(f"Error processing merged branch cleanup for project {project_id}: {e}")


async def gitlab_mr_jira_validator_task():
    """
    Iterates over tracked GitLab projects and fetches open Merge Requests.
    Checks if the MR title contains a Jira task ID.
    If missing, and if no automated reminder has been sent yet, posts a comment
    (in Russian) asking to add the Jira task ID.
    """

    import logging
    import re

    logger = logging.getLogger(__name__)
    logger.info("Starting GitLab MR Jira validator task...")

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_MR_JIRA_VALIDATOR_REMINDER -->"
    jira_id_pattern = re.compile(r'[A-Z]+-\d+')

    for project_id in tracked_projects:
        try:
            gitlab_client = GitLabClient()
            mrs = gitlab_client.get_project_merge_requests(project_id, state="opened")
            for mr in mrs:
                try:
                    if jira_id_pattern.search(mr.title):
                        continue

                    # Check if we already posted a reminder
                    notes = mr.notes.list(all=True)
                    has_reminder = False
                    for note in notes:
                        if reminder_marker in note.body:
                            has_reminder = True
                            break

                    if not has_reminder:
                        message = f"Пожалуйста, добавьте идентификатор задачи Jira в название Merge Request.\n\n{reminder_marker}"
                        gitlab_client.create_mr_note(project_id, mr.iid, message)
                        logger.info(f"Added Jira validator reminder to MR !{mr.iid} in project {project_id}")

                except Exception as e:
                    logger.error(f"Error validating MR !{mr.iid} in project {project_id}: {e}")
        except Exception as e:
            logger.error(f"Error processing MR Jira validator for project {project_id}: {e}")

    return "MR Jira validator task completed"


async def gitlab_mr_conflict_notifier_task():
    """
    Iterates over open MRs for tracked projects.
    If an MR has merge conflicts, checks if a reminder has been sent.
    If not, generates a polite notification via LLM in Russian asking to resolve the conflicts.
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting GitLab MR conflict notifier task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping GitLab MR conflict notifier.")
        return "GitLab MR conflict notifier task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)

    gitlab_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    gitlab_projects = [p.strip() for p in gitlab_projects if p.strip()]

    client = GitLabClient()
    reminder_marker = "<!-- AUTO_GENERATED_MR_CONFLICT_NOTIFIER -->"

    for project_id in gitlab_projects:
        try:
            project = client.client.projects.get(project_id)
            mrs = project.mergerequests.list(state='opened', get_all=True)

            for mr in mrs:
                if hasattr(mr, "has_conflicts") and mr.has_conflicts:
                    mr_notes = mr.notes.list(get_all=True)
                    already_notified = any(reminder_marker in note.body for note in mr_notes)

                    if not already_notified:
                        prompt = (
                            f"Generate a very short, polite comment in Russian to notify the author of the Merge Request "
                            f"'{mr.title}' that their MR has merge conflicts and they need to resolve them so it can be reviewed/merged. "
                            f"Include this exact invisible HTML marker anywhere in your response: {reminder_marker}"
                        )
                        response = await llm.ainvoke(prompt)
                        comment_body = response.content

                        client.create_mr_note(project_id, mr.iid, comment_body)
                        logger.info(f"Posted MR conflict reminder to MR {mr.iid} in project {project_id}.")

        except Exception as e:
            logger.error(f"Error processing MR conflict notifier for GitLab project {project_id}: {e}")

    logger.info("Finished GitLab MR conflict notifier task.")
    return "GitLab MR conflict notifier task completed"


async def gitlab_mr_missing_description_notifier_task():
    """
    Iterates over open MRs for tracked projects.
    If an MR has an empty or very short description, checks if a reminder has been sent.
    If not, generates a polite notification via LLM in Russian asking to add a description.
    """
    import logging
    # Use global imports so mocker can patch them in app.tasks
    global GitLabClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting GitLab empty MR description notifier task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping empty MR description notifier.")
        return "GitLab empty MR description notifier task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)

    gitlab_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    gitlab_projects = [p.strip() for p in gitlab_projects if p.strip()]

    client = GitLabClient()
    reminder_marker = "<!-- AUTO_GENERATED_EMPTY_MR_DESCRIPTION_NOTIFIER -->"

    for project_id in gitlab_projects:
        try:
            project = client.client.projects.get(project_id)
            mrs = project.mergerequests.list(state='opened', get_all=True)

            for mr in mrs:
                description = mr.description or ""
                if len(description.strip()) < 10:
                    mr_notes = mr.notes.list(get_all=True)
                    already_notified = any(reminder_marker in note.body for note in mr_notes)

                    if not already_notified:
                        prompt = (
                            f"Generate a very short, polite comment in Russian to notify the author of the Merge Request "
                            f"'{mr.title}' that their MR has an empty or very short description. Ask them to add a proper "
                            f"description to help reviewers understand the changes. "
                            f"Include this exact invisible HTML marker anywhere in your response: {reminder_marker}"
                        )
                        response = await llm.ainvoke(prompt)
                        comment_body = response.content

                        client.create_mr_note(project_id, mr.iid, comment_body)
                        logger.info(f"Added empty MR description reminder to MR {mr.iid} in project {project_id}")
        except Exception as e:
            logger.error(f"Error processing project {project_id} in empty MR description notifier task: {e}")

    logger.info("Finished GitLab empty MR description notifier task.")
    return "GitLab empty MR description notifier task completed"

async def jira_missing_estimation_reminder_task():
    """
    Checks Jira tasks in active sprints and leaves a comment if they lack story point estimations.
    """
    logger.info("Running Jira missing estimation reminder task.")

    openai_api_key = settings.get("OPENAI_API_KEY")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not set. Skipping missing estimation reminder task.")
        return "Jira missing estimation reminder task skipped (no OpenAI API key)"

    jira_client = JiraClient()
    jira_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    story_points_field = settings.get("JIRA_STORY_POINTS_FIELD", "customfield_10016")

    llm = ChatOpenAI(temperature=0.7, model="gpt-4o-mini", api_key=openai_api_key)

    for j_proj in jira_projects:
        j_proj = j_proj.strip()
        if not j_proj:
            continue

        jql = f'project = "{j_proj}" AND sprint in openSprints()'
        try:
            issues = jira_client.search_issues(jql)
        except Exception as e:
            logger.error(f"Error fetching issues for project {j_proj}: {e}")
            continue

        for issue in issues:
            # Check for estimation
            story_points = getattr(issue.fields, story_points_field, None)
            time_estimate = getattr(issue.fields, "timeoriginalestimate", None)

            if story_points is not None or time_estimate is not None:
                continue # Task has estimation

            # Task is missing estimation
            try:
                comments = jira_client.get_comments(issue.key)
                already_reminded = any("<!-- AUTO_GENERATED_JIRA_MISSING_ESTIMATION_REMINDER -->" in getattr(c, "body", "") for c in comments)

                if already_reminded:
                    continue

                prompt = [
                    SystemMessage(content="You are an AI assistant helping a technical leader manage Jira tasks."),
                    HumanMessage(content=f"Сгенерируй короткое вежливое напоминание (на русском языке) для исполнителя задачи о том, что в задаче не указана оценка (Story Points или первоначальная оценка времени). Попроси добавить оценку. Задача в активном спринте. Не используй приветствие, просто текст напоминания. Задача: {issue.key} - {issue.fields.summary}")
                ]

                response = llm.invoke(prompt)
                comment_body = response.content.strip()

                final_comment = f"<!-- AUTO_GENERATED_JIRA_MISSING_ESTIMATION_REMINDER -->\n{comment_body}"

                jira_client.add_comment(issue.key, final_comment)
                logger.info(f"Added missing estimation reminder for Jira task {issue.key}")

            except Exception as e:
                logger.error(f"Error processing missing estimation reminder for issue {issue.key}: {e}")

    return "Jira missing estimation reminder task completed"

async def gitlab_unresolved_threads_reminder_task():
    """
    Iterates over open MRs for tracked projects.
    Checks for discussions (threads) that are unresolved and have not been updated for 3+ days.
    Generates a gentle reminder via LLM (in Russian) and posts it as a reply to the thread.
    """
    import logging
    from datetime import datetime, timezone
    import dateutil.parser
    global GitLabClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting GitLab unresolved threads reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping unresolved threads reminder.")
        return "GitLab unresolved threads reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)

    gitlab_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    gitlab_projects = [p.strip() for p in gitlab_projects if p.strip()]

    client = GitLabClient()
    reminder_marker = "<!-- AUTO_GENERATED_UNRESOLVED_THREAD_REMINDER -->"
    now = datetime.now(timezone.utc)

    for project_id in gitlab_projects:
        try:
            project = client.client.projects.get(project_id)
            mrs = project.mergerequests.list(state='opened', get_all=True)

            for mr in mrs:
                try:
                    discussions = mr.discussions.list(get_all=True)
                    for discussion in discussions:
                        notes = discussion.attributes.get('notes', [])
                        if not notes:
                            continue

                        first_note = notes[0]
                        if not first_note.get('resolvable'):
                            continue

                        is_resolved = any(n.get('resolved', False) for n in notes)
                        if is_resolved:
                            continue

                        last_updated_str = max((n.get('updated_at') for n in notes if n.get('updated_at')), default=None)
                        if not last_updated_str:
                            continue

                        last_updated = dateutil.parser.isoparse(last_updated_str)
                        days_inactive = (now - last_updated).days

                        if days_inactive > 3:
                            already_reminded = any(reminder_marker in note.get('body', '') for note in notes)
                            if not already_reminded:
                                prompt = (
                                    f"Generate a short, polite comment in Russian to remind the team about an unresolved discussion "
                                    f"in the Merge Request '{mr.title}' that hasn't been updated for {days_inactive} days. "
                                    f"Ask them to resolve it or continue the conversation. "
                                    f"Include this exact invisible HTML marker anywhere in your response: {reminder_marker}"
                                )
                                response = await llm.ainvoke(prompt)
                                discussion.notes.create({'body': response.content})
                                logger.info(f"Added unresolved thread reminder to MR {mr.iid} in project {project_id}")
                except Exception as e:
                    logger.error(f"Error checking discussions for MR {mr.iid} in project {project_id}: {e}")
        except Exception as e:
            logger.error(f"Error processing project {project_id} in unresolved threads reminder task: {e}")

    logger.info("Finished GitLab unresolved threads reminder task.")
    return "GitLab unresolved threads reminder task completed"

async def gitlab_mr_cicd_failure_notifier_task():
    """
    Iterates over open MRs for tracked projects.
    Checks if the latest CI pipeline failed and the author hasn't been notified yet.
    Generates a polite notification via LLM in Russian to fix the CI.
    """
    import logging
    global GitLabClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting GitLab MR CI/CD failure notifier task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping GitLab MR CI/CD failure notifier.")
        return "GitLab MR CI/CD failure notifier task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)

    gitlab_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    gitlab_projects = [p.strip() for p in gitlab_projects if p.strip()]

    client = GitLabClient()

    for project_id in gitlab_projects:
        try:
            project = client.client.projects.get(project_id)
            mrs = project.mergerequests.list(state='opened', get_all=True)

            for mr in mrs:
                try:
                    pipelines = mr.pipelines.list(get_all=False, per_page=1)
                    if not pipelines:
                        continue

                    latest_pipeline = pipelines[0]
                    if latest_pipeline.status != 'failed':
                        continue

                    reminder_marker = f"<!-- AUTO_GENERATED_CI_FAILURE_NOTIFIER_{latest_pipeline.id} -->"
                    mr_notes = mr.notes.list(get_all=True)
                    already_notified = any(reminder_marker in note.body for note in mr_notes)

                    if not already_notified:
                        prompt = (
                            f"Сгенерируй очень короткое, вежливое сообщение на русском языке автору Merge Request "
                            f"с названием '{mr.title}', в котором нужно сказать, что последний CI/CD пайплайн упал (статус failed) "
                            f"и нужно исправить ошибки, чтобы MR можно было проверить и вмержить.\n"
                            f"Добавь этот невидимый HTML маркер где-нибудь в своем ответе: {reminder_marker}"
                        )
                        response = await llm.ainvoke(prompt)
                        comment_body = response.content

                        client.create_mr_note(project_id, mr.iid, comment_body)
                        logger.info(f"Posted CI/CD failure reminder for pipeline {latest_pipeline.id} to MR {mr.iid} in project {project_id}.")
                except Exception as e:
                    logger.error(f"Error processing CI/CD pipeline for MR {mr.iid} in project {project_id}: {e}")

        except Exception as e:
            logger.error(f"Error processing MR CI/CD failure notifier for GitLab project {project_id}: {e}")

    logger.info("Finished GitLab MR CI/CD failure notifier task.")
    return "GitLab MR CI/CD failure notifier task completed"


async def jira_missing_acceptance_criteria_reminder_task():
    """
    Checks Jira tasks in active sprints and leaves a comment if they lack 'Acceptance Criteria'.
    """
    import logging
    from langchain_core.messages import SystemMessage, HumanMessage
    global JiraClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Running Jira missing acceptance criteria reminder task.")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not set. Skipping missing acceptance criteria reminder task.")
        return "Jira missing acceptance criteria reminder task skipped (no OpenAI API key)"

    jira_client = JiraClient()
    jira_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")

    llm = ChatOpenAI(temperature=0.7, model="gpt-4o-mini", api_key=openai_api_key)
    reminder_marker = "<!-- AUTO_GENERATED_JIRA_MISSING_AC_REMINDER -->"

    for j_proj in jira_projects:
        j_proj = j_proj.strip()
        if not j_proj:
            continue

        jql = f'project = "{j_proj}" AND sprint in openSprints()'
        try:
            issues = jira_client.search_issues(jql)
        except Exception as e:
            logger.error(f"Error fetching issues for project {j_proj}: {e}")
            continue

        for issue in issues:
            description = getattr(issue.fields, "description", "") or ""
            description_lower = description.lower()

            if "acceptance criteria" in description_lower or "критерии приемки" in description_lower:
                continue # Task has acceptance criteria

            # Task is missing AC
            try:
                comments_obj = jira_client.get_comments(issue.key)
                # Jira API might return a dict or object depending on implementation, jira package returns object with comments list
                # Actually, jira_client.get_comments returns list of comment objects
                already_reminded = any(reminder_marker in getattr(c, "body", "") for c in comments_obj)

                if already_reminded:
                    continue

                prompt = [
                    SystemMessage(content="You are an AI assistant helping a technical leader manage Jira tasks."),
                    HumanMessage(content=f"Сгенерируй короткое вежливое напоминание (на русском языке) для исполнителя задачи о том, что в описании задачи отсутствуют 'Критерии приемки' (Acceptance Criteria). Попроси их добавить, чтобы было понятно, когда задача считается выполненной. Не используй приветствие, просто текст напоминания. Задача: {issue.key} - {issue.fields.summary}.\nВ конце добавь невидимый маркер: {reminder_marker}")
                ]

                response = llm.invoke(prompt)
                jira_client.add_comment(issue.key, response.content)
                logger.info(f"Added missing acceptance criteria reminder to {issue.key}")

            except Exception as e:
                logger.error(f"Error processing missing acceptance criteria for issue {issue.key}: {e}")

    logger.info("Finished Jira missing acceptance criteria reminder task.")
    return "Jira missing acceptance criteria reminder task completed"

async def gitlab_mr_too_many_comments_notifier_task():
    """
    Iterates over open MRs for tracked projects.
    Checks if the number of discussions exceeds a threshold (15).
    If so, and no automated reminder has been sent, posts a comment suggesting a synchronous meeting.
    """
    import logging



    logger = logging.getLogger(__name__)
    logger.info("Starting GitLab MR too many comments notifier task...")

    gitlab_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    gitlab_projects = [p.strip() for p in gitlab_projects if p.strip()]

    threshold = 15
    reminder_marker = "<!-- AUTO_GENERATED_TOO_MANY_COMMENTS -->"

    for project_id in gitlab_projects:
        try:
            client = GitLabClient()
            project = client.client.projects.get(project_id)
            mrs = project.mergerequests.list(state='opened', get_all=True)

            for mr in mrs:
                try:
                    discussions = mr.discussions.list(get_all=True)
                    user_discussions_count = 0

                    for discussion in discussions:
                        notes = discussion.attributes.get('notes', [])
                        if not notes:
                            continue

                        first_note = notes[0]
                        if first_note.get('resolvable', False):
                            user_discussions_count += 1

                    if user_discussions_count > threshold:
                        # Check if reminder already posted
                        notes = mr.notes.list(get_all=True)
                        already_reminded = any(reminder_marker in getattr(n, 'body', '') for n in notes)

                        if not already_reminded:
                            message = (
                                f"В этом Merge Request накопилось уже много обсуждений ({user_discussions_count}). "
                                f"Возможно, стоит обсудить оставшиеся вопросы на коротком созвоне?\n\n{reminder_marker}"
                            )
                            client.create_mr_note(project_id, mr.iid, message)
                            logger.info(f"Added too many comments reminder to MR !{mr.iid} in project {project_id}")

                except Exception as e:
                    logger.error(f"Error checking comments for MR {mr.iid} in project {project_id}: {e}")
        except Exception as e:
            logger.error(f"Error processing project {project_id} in MR too many comments notifier task: {e}")

    logger.info("Finished GitLab MR too many comments notifier task.")
    return "GitLab MR too many comments notifier task completed"

async def jira_overdue_task_reminder_task():
    """
    Checks Jira tasks in active sprints and leaves a comment if they are overdue.
    """
    import logging
    from datetime import datetime, timezone
    import dateutil.parser


    logger = logging.getLogger(__name__)
    logger.info("Running Jira overdue task reminder task.")

    jira_client = JiraClient()
    jira_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    reminder_marker = "<!-- AUTO_GENERATED_OVERDUE_REMINDER -->"
    now = datetime.now(timezone.utc)

    for j_proj in jira_projects:
        j_proj = j_proj.strip()
        if not j_proj:
            continue

        jql = f'project = "{j_proj}" AND sprint in openSprints()'
        try:
            issues = jira_client.search_issues(jql)
        except Exception as e:
            logger.error(f"Error fetching issues for project {j_proj}: {e}")
            continue

        for issue in issues:
            try:
                due_date_str = getattr(issue.fields, "duedate", None)
                if not due_date_str:
                    continue

                due_date = dateutil.parser.isoparse(due_date_str)
                # Ensure timezone aware
                if due_date.tzinfo is None:
                    due_date = due_date.replace(tzinfo=timezone.utc)

                if due_date < now:
                    comments = jira_client.get_comments(issue.key)
                    already_reminded = any(reminder_marker in getattr(c, "body", "") for c in comments)

                    if not already_reminded:
                        message = (
                            f"Срок выполнения этой задачи прошел ({due_date_str}). "
                            f"Пожалуйста, актуализируйте статус задачи или измените срок выполнения.\n\n{reminder_marker}"
                        )
                        jira_client.add_comment(issue.key, message)
                        logger.info(f"Added overdue reminder to Jira task {issue.key}")

            except Exception as e:
                logger.error(f"Error processing overdue reminder for issue {issue.key}: {e}")

    logger.info("Finished Jira overdue task reminder task.")
    return "Jira overdue task reminder task completed"


async def gitlab_mr_missing_tests_notifier_task():
    """
    Checks open Merge Requests for modified source files without corresponding modifications to test files.
    If tests are missing, uses an LLM to generate a polite notification (in Russian) and posts it.
    """
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Starting automated GitLab MR missing tests notifier task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping GitLab MR missing tests notifier.")
        return "GitLab MR missing tests notifier task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_MR_MISSING_TESTS_NOTIFIER -->"
    gitlab_client = GitLabClient()

    for project_id in tracked_projects:
        logger.info(f"Checking missing tests for MRs in project {project_id}")
        mrs = gitlab_client.get_merge_requests(project_id, state="opened")

        # We need the specific MR object to fetch changes
        try:
            gl_project = gitlab_client.client.projects.get(project_id)
        except Exception as e:
            logger.error(f"Could not fetch project {project_id}: {e}")
            continue

        for mr in mrs:
            try:
                full_mr = gl_project.mergerequests.get(mr.iid)
                changes = full_mr.changes()

                has_source_changes = False
                has_test_changes = False

                for change in changes.get("changes", []):
                    new_path = change.get("new_path", "")
                    # Simple heuristic for test files vs source files
                    is_test_file = "test" in new_path.lower() or new_path.startswith("tests/")
                    is_source_file = new_path.endswith((".py", ".js", ".ts", ".go", ".java", ".cpp", ".c", ".cs"))

                    if is_test_file:
                        has_test_changes = True
                    elif is_source_file:
                        has_source_changes = True

                if has_source_changes and not has_test_changes:
                    # Check if we already reminded
                    notes = full_mr.notes.list(all=True)
                    already_notified = any(reminder_marker in getattr(n, "body", "") for n in notes)

                    if not already_notified:
                        prompt = (
                            "Вы — технический лидер. Напишите очень короткое, вежливое сообщение "
                            "автору Merge Request, обратив внимание на то, что в MR есть изменения исходного кода, "
                            "но нет изменений в файлах тестов. Предложите добавить тесты для нового кода или "
                            "обновить существующие. Сообщение должно быть на русском языке."
                        )
                        response = llm.invoke([HumanMessage(content=prompt)])
                        message_body = f"{response.content}\n\n{reminder_marker}"

                        gitlab_client.create_mr_note(project_id, mr.iid, message_body)
                        logger.info(f"Added missing tests notification to MR !{mr.iid} in project {project_id}")

            except Exception as e:
                logger.error(f"Error checking tests for MR !{mr.iid} in project {project_id}: {e}")

    logger.info("Finished GitLab MR missing tests notifier task.")
    return "GitLab MR missing tests notifier task completed"


async def jira_missing_description_reminder_task():
    """
    Checks non-closed Jira issues. If the description is empty or very short,
    generates a polite reminder asking the reporter/assignee to provide a detailed description.
    """
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Starting automated Jira missing description reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping Jira missing description reminder.")
        return "Jira missing description reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    jira_client = JiraClient()
    tracked_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_JIRA_MISSING_DESCRIPTION_REMINDER -->"

    for project_key in tracked_projects:
        jql = f'project = "{project_key}" AND statusCategory != Done'
        issues = jira_client.search_issues(jql)
        logger.info(f"Found {len(issues)} active issues in project {project_key} to check for descriptions")

        for issue in issues:
            try:
                description = getattr(issue.fields, "description", None)

                # Check if description is missing or very short
                if not description or len(description.strip()) < 20:
                    comments = jira_client.get_comments(issue.key)
                    already_reminded = any(reminder_marker in getattr(c, "body", "") for c in comments)

                    if not already_reminded:
                        prompt = (
                            "Вы — технический лидер (Tech Lead). "
                            "Напишите короткое, вежливое сообщение автору или исполнителю задачи в Jira, "
                            "указав, что описание задачи пустое или слишком короткое. "
                            "Попросите добавить подробное описание, чтобы всем был понятен контекст задачи. "
                            "Сообщение должно быть на русском языке."
                        )
                        response = llm.invoke([HumanMessage(content=prompt)])
                        message = f"{response.content}\n\n{reminder_marker}"

                        jira_client.add_comment(issue.key, message)
                        logger.info(f"Added missing description reminder to Jira task {issue.key}")

            except Exception as e:
                logger.error(f"Error processing missing description for issue {issue.key}: {e}")

    logger.info("Finished Jira missing description reminder task.")
    return "Jira missing description reminder task completed"

async def gitlab_mr_missing_reviewer_notifier_task():
    """
    Iterates over open MRs for tracked projects.
    If an MR is not draft and has no reviewers assigned, checks if a reminder has been sent.
    If not, generates a polite notification via LLM in Russian asking to assign a reviewer.
    """
    import logging
    # Use global imports so mocker can patch them in app.tasks
    global GitLabClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting GitLab MR missing reviewer notifier task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping MR missing reviewer notifier.")
        return "GitLab MR missing reviewer notifier task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)

    gitlab_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    gitlab_projects = [p.strip() for p in gitlab_projects if p.strip()]

    client = GitLabClient()
    reminder_marker = "<!-- AUTO_GENERATED_MR_MISSING_REVIEWER_NOTIFIER -->"

    for project_id in gitlab_projects:
        try:
            project = client.client.projects.get(project_id)
            mrs = project.mergerequests.list(state='opened', get_all=True)

            for mr in mrs:
                if mr.draft or mr.reviewers:
                    continue

                mr_notes = mr.notes.list(get_all=True)
                already_notified = any(reminder_marker in note.body for note in mr_notes)

                if not already_notified:
                    prompt = (
                        f"Generate a very short, polite comment in Russian to notify the author of the Merge Request "
                        f"'{mr.title}' that their MR is ready for review but has no reviewers assigned. Ask them to assign at least one reviewer. "
                        f"Include this exact invisible HTML marker anywhere in your response: {reminder_marker}"
                    )
                    response = await llm.ainvoke(prompt)
                    comment_body = response.content

                    client.create_mr_note(project_id, mr.iid, comment_body)
                    logger.info(f"Added missing reviewer reminder to MR {mr.iid} in project {project_id}")
        except Exception as e:
            logger.error(f"Error processing project {project_id} in missing reviewer notifier task: {e}")

async def jira_weekly_sprint_summary_task():
    """
    Fetches Jira tasks for active sprints, categorizes them by completion status,
    generates a summary using LLM in Russian, and posts it to Confluence.
    """
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Starting Jira weekly sprint summary task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping weekly sprint summary.")
        return "Jira weekly sprint summary task skipped (no OpenAI API key)"

    confluence_space = settings.get("CONFLUENCE_TRACKED_SPACES", "").split(",")
    if not confluence_space or not confluence_space[0].strip():
        logger.warning("No confluence spaces tracked for sprint summary.")
        return "Jira weekly sprint summary task skipped (no spaces)"

    space = confluence_space[0].strip()

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    jira_client = JiraClient()
    confluence_client = ConfluenceClient()

    tracked_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    for project_key in tracked_projects:
        jql = f'project = "{project_key}" AND sprint in openSprints()'
        try:
            issues = jira_client.search_issues(jql)
        except Exception as e:
            logger.error(f"Error fetching active sprint issues for project {project_key}: {e}")
            continue

        if not issues:
            logger.info(f"No active sprint issues found for project {project_key}")
            continue

        completed_tasks = []
        pending_tasks = []

        for issue in issues:
            summary = getattr(issue.fields, "summary", "")
            status = getattr(issue.fields.status, "name", "")
            status_category = getattr(issue.fields.status.statusCategory, "name", "")

            task_info = f"- [{issue.key}] {summary} (Статус: {status})"

            if status_category == "Done":
                completed_tasks.append(task_info)
            else:
                pending_tasks.append(task_info)

        prompt_text = (
            f"Ты — технический лидер. Подготовь еженедельный отчет по текущему спринту для проекта {project_key}.\n\n"
            f"Выполненные задачи:\n{chr(10).join(completed_tasks) if completed_tasks else 'Нет выполненных задач'}\n\n"
            f"Задачи в работе (ожидающие завершения):\n{chr(10).join(pending_tasks) if pending_tasks else 'Нет задач в работе'}\n\n"
            "Сгенерируй отчет в формате HTML, который можно напрямую вставить на страницу Confluence (без тегов `<html>`, `<body>`, или markdown блоков вроде ```html). "
            "Отчет должен быть структурированным, легко читаемым, на русском языке. Можешь добавить краткое ободряющее слово для команды в начале или в конце."
        )

        try:
            from langchain_core.messages import HumanMessage
            response = llm.invoke([HumanMessage(content=prompt_text)])
            html_content = response.content

            if html_content.startswith("```html"):
                html_content = html_content[7:]
            if html_content.endswith("```"):
                html_content = html_content[:-3]

            title = f"Еженедельный отчет по спринту: {project_key}"

            confluence_client.client.create_page(
                space=space,
                title=title,
                body=html_content.strip(),
                parent_id=None
            )
            logger.info(f"Published sprint summary for {project_key} to space {space}.")
        except Exception as e:
            logger.error(f"Error generating or publishing sprint summary for project {project_key}: {e}")

    logger.info("Finished Jira weekly sprint summary task.")
    return "Jira weekly sprint summary task completed"

async def jira_sprint_unassigned_task_reminder_task():
    """
    Checks Jira tasks in active sprints that are not assigned to anyone,
    and posts a comment asking the team to assign the task.
    """
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Starting automated Jira sprint unassigned task reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping Jira sprint unassigned task reminder.")
        return "Jira sprint unassigned task reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    jira_client = JiraClient()
    tracked_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_JIRA_SPRINT_UNASSIGNED_TASK_REMINDER -->"

    for project_key in tracked_projects:
        jql = f'project = "{project_key}" AND sprint in openSprints() AND assignee IS EMPTY AND statusCategory != Done'
        issues = jira_client.search_issues(jql)
        logger.info(f"Found {len(issues)} unassigned active issues in open sprints in project {project_key}")

        for issue in issues:
            try:
                comments = jira_client.get_comments(issue.key)
                already_reminded = any(reminder_marker in getattr(c, "body", "") for c in comments)

                if not already_reminded:
                    prompt = (
                        "Вы — технический лидер (Tech Lead). "
                        "Напишите короткое, вежливое сообщение команде в комментариях задачи Jira, "
                        "которая находится в активном спринте, но на данный момент ни на кого не назначена. "
                        "Попросите кого-нибудь взять задачу в работу или назначить ответственного, "
                        "чтобы она не потерялась. Сообщение должно быть на русском языке."
                    )
                    response = llm.invoke([HumanMessage(content=prompt)])
                    message = f"{response.content}\n\n{reminder_marker}"

                    jira_client.add_comment(issue.key, message)
                    logger.info(f"Added unassigned task reminder to Jira task {issue.key}")

            except Exception as e:
                logger.error(f"Error processing unassigned task reminder for issue {issue.key}: {e}")

    logger.info("Finished Jira sprint unassigned task reminder task.")
    return "Jira sprint unassigned task reminder task completed"

async def gitlab_mr_title_linter_task():
    """
    Checks GitLab Merge Request titles for compliance with standard conventions
    (e.g., Conventional Commits or Jira ticket prefixes).
    If a title is non-compliant, uses the LLM to generate a polite reminder in Russian
    and posts it to the MR, avoiding duplicate comments via a hidden marker.
    """
    import logging
    import re

    global GitLabClient, ChatOpenAI, settings, HumanMessage

    logger = logging.getLogger(__name__)
    logger.info("Starting automated GitLab MR title linter task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping MR title linter.")
        return "MR title linter task skipped (no OpenAI API key)"

    marker = "<!-- AUTO_GENERATED_MR_TITLE_LINTER_REMINDER -->"
    gitlab_client = GitLabClient()
    llm = ChatOpenAI(temperature=0.7, model="gpt-4o-mini", api_key=openai_api_key)

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")

    # Regex for Conventional Commits or Jira ID prefix
    # e.g., "feat(ui): ...", "fix: ...", "TLA-123 Fix ..."
    pattern = r"^(feat|fix|docs|style|refactor|perf|test|chore|build|ci|revert)(\([a-zA-Z0-9_-]+\))?: .+|^[A-Z]+-[0-9]+ .+"

    for project_id in tracked_projects:
        project_id = project_id.strip()
        if not project_id:
            continue

        try:
            mrs = gitlab_client.get_open_merge_requests(project_id)
            for mr in mrs:
                title = mr.title

                # Exclude drafts from strict title linting to be flexible, but optional.
                if mr.draft or title.lower().startswith("draft:"):
                    continue

                if re.match(pattern, title):
                    continue

                try:
                    notes = gitlab_client.get_mr_notes(project_id, mr.iid)
                    already_reminded = any(marker in (note.body or "") for note in notes)

                    if not already_reminded:
                        prompt = (
                            f"Вы — технический лидер (Tech Lead). Название Merge Request '{title}' "
                            f"не соответствует принятым стандартам именования (Conventional Commits или префикс задачи Jira, например 'TLA-123 ...'). "
                            f"Напишите короткое, вежливое сообщение автору, попросив его привести название к стандарту. "
                            f"Приведите пару примеров правильных названий (например, 'feat(auth): добавлена авторизация' или 'TLA-123 Исправление ошибки авторизации'). "
                            f"Сообщение должно быть на русском языке."
                        )
                        response = llm.invoke([HumanMessage(content=prompt)])
                        message = f"{response.content}\n\n{marker}"

                        gitlab_client.create_mr_note(project_id, mr.iid, message)
                        logger.info(f"Posted title linter reminder on MR {mr.iid} in project {project_id}")
                except Exception as e:
                    logger.error(f"Error processing MR {mr.iid} in project {project_id} for title linter: {e}")

        except Exception as e:
            logger.error(f"Error fetching MRs for project {project_id} in title linter: {e}")

    logger.info("Finished automated GitLab MR title linter task.")
    return "GitLab MR title linter task completed"

async def jira_missing_component_reminder_task():
    """
    Checks Jira tasks in active sprints that do not have an assigned component,
    and posts a comment asking the author to assign one.
    """
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Starting automated Jira missing component reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping Jira missing component reminder.")
        return "Jira missing component reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    jira_client = JiraClient()
    tracked_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_JIRA_MISSING_COMPONENT_REMINDER -->"

    for project_key in tracked_projects:
        jql = f'project = "{project_key}" AND sprint in openSprints() AND components IS EMPTY AND statusCategory != Done'
        issues = jira_client.search_issues(jql)
        logger.info(f"Found {len(issues)} issues missing components in open sprints in project {project_key}")

        for issue in issues:
            try:
                comments = jira_client.get_comments(issue.key)
                already_reminded = any(reminder_marker in getattr(c, "body", "") for c in comments)

                if not already_reminded:
                    prompt = (
                        "Вы — технический лидер (Tech Lead). "
                        "Напишите короткое, вежливое сообщение автору задачи Jira, "
                        "которая находится в активном спринте, но не имеет назначенного компонента. "
                        "Попросите добавить компонент (component), чтобы задача была правильно классифицирована. "
                        "Сообщение должно быть на русском языке."
                    )
                    response = llm.invoke([HumanMessage(content=prompt)])
                    message = f"{response.content}\n\n{reminder_marker}"

                    jira_client.add_comment(issue.key, message)
                    logger.info(f"Added missing component reminder to Jira task {issue.key}")

            except Exception as e:
                logger.error(f"Error processing missing component reminder for issue {issue.key}: {e}")

    logger.info("Finished Jira missing component reminder task.")
    return "Jira missing component reminder task completed"

async def jira_missing_fixversion_reminder_task():
    """
    Checks Jira tasks that are completed/resolved but do not have an assigned fixVersion,
    and posts a comment asking the author to assign one.
    """
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Starting automated Jira missing fixVersion reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping Jira missing fixVersion reminder.")
        return "Jira missing fixVersion reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    jira_client = JiraClient()
    tracked_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_JIRA_MISSING_FIXVERSION_REMINDER -->"

    for project_key in tracked_projects:
        jql = f'project = "{project_key}" AND statusCategory = Done AND fixVersion is EMPTY'
        issues = jira_client.search_issues(jql)
        logger.info(f"Found {len(issues)} completed issues missing fixVersion in project {project_key}")

        for issue in issues:
            try:
                comments = jira_client.get_comments(issue.key)
                already_reminded = any(reminder_marker in getattr(c, "body", "") for c in comments)

                if not already_reminded:
                    prompt = (
                        "Вы — технический лидер (Tech Lead). "
                        "Напишите короткое, вежливое сообщение автору выполненной (Done/Resolved) задачи Jira, "
                        "у которой не проставлен релиз (fixVersion). "
                        "Попросите добавить fixVersion, чтобы задача попала в список изменений (release notes). "
                        "Сообщение должно быть на русском языке."
                    )
                    response = llm.invoke([HumanMessage(content=prompt)])
                    message = f"{response.content}\n\n{reminder_marker}"

                    jira_client.add_comment(issue.key, message)
                    logger.info(f"Added missing fixVersion reminder to Jira task {issue.key}")

            except Exception as e:
                logger.error(f"Error processing missing fixVersion reminder for issue {issue.key}: {e}")

    logger.info("Finished Jira missing fixVersion reminder task.")
    return "Jira missing fixVersion reminder task completed"

async def gitlab_long_running_mr_reminder_task():
    """
    Checks if a GitLab Merge Request has been open for an unusually long time (> 14 days)
    and notifies the authors to break it down or close it if no longer relevant.
    """
    from datetime import datetime, timezone
    import logging

    global GitLabClient, ChatOpenAI, settings, HumanMessage

    logger = logging.getLogger(__name__)
    logger.info("Starting automated GitLab long-running MR reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping long-running MR reminder.")
        return "GitLab long-running MR reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7, openai_api_key=openai_api_key)
    gitlab_client = GitLabClient()

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_LONG_RUNNING_MR_REMINDER -->"
    now = datetime.now(timezone.utc)

    for project_id in tracked_projects:
        try:
            mrs = gitlab_client.get_project_merge_requests(project_id, state="opened")
            for mr in mrs:
                try:
                    # Check created_at
                    # GitLab's created_at format is ISO 8601, e.g. "2023-01-01T12:00:00.000Z"
                    created_at_str = mr.created_at
                    # Replace Z with +00:00 for fromisoformat compatibility in python < 3.11
                    if created_at_str.endswith('Z'):
                        created_at_str = created_at_str[:-1] + '+00:00'
                    created_at = datetime.fromisoformat(created_at_str)

                    days_open = (now - created_at).days
                    if days_open <= 14:
                        continue

                    notes = mr.notes.list(all=True)
                    already_reminded = any(reminder_marker in getattr(note, 'body', '') for note in notes)
                    if already_reminded:
                        continue

                    prompt = (
                        f"Ты - вежливый технический помощник. Пожалуйста, напиши дружелюбное напоминание для автора "
                        f"о Merge Request, который открыт уже {days_open} дней. "
                        f"Заголовок MR: '{mr.title}'. "
                        f"Предложи автору разбить MR на более мелкие части, чтобы ускорить ревью, "
                        f"или закрыть его, если он больше не актуален. "
                        f"Используй русский язык."
                    )

                    response = llm.invoke([HumanMessage(content=prompt)])

                    note_body = f"{response.content}\n\n{reminder_marker}"
                    gitlab_client.create_mr_note(project_id, mr.iid, note_body)
                    logger.info(f"Added long-running MR reminder to MR {mr.iid} in project {project_id}")

                except Exception as e:
                    logger.error(f"Error checking long-running MR {mr.iid} in project {project_id}: {e}")
        except Exception as e:
            logger.error(f"Error processing long-running MR reminder for project {project_id}: {e}")

    logger.info("Finished automated GitLab long-running MR reminder task.")
    return "GitLab long-running MR reminder task completed"

async def jira_inactive_reporter_reminder_task():
    """
    Checks Jira tasks that have been resolved for 3 days but haven't been closed/verified by the reporter,
    and posts a comment tagging the reporter to verify and close the issue.
    """
    import logging
    from langchain_core.messages import HumanMessage


    logger = logging.getLogger(__name__)
    logger.info("Starting automated Jira inactive reporter reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping Jira inactive reporter reminder.")
        return "Jira inactive reporter reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    jira_client = JiraClient()
    tracked_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_JIRA_INACTIVE_REPORTER_REMINDER -->"

    for project_key in tracked_projects:
        jql = f'project = "{project_key}" AND status = "Resolved" AND updated <= -3d'
        issues = jira_client.search_issues(jql)
        logger.info(f"Found {len(issues)} resolved issues inactive for 3 days in project {project_key}")

        for issue in issues:
            try:
                comments = jira_client.get_comments(issue.key)
                already_reminded = any(reminder_marker in getattr(c, "body", "") for c in comments)

                if not already_reminded:
                    reporter_name = getattr(issue.fields.reporter, "displayName", "Reporter") if hasattr(issue.fields, "reporter") and issue.fields.reporter else "Reporter"
                    reporter_mention = f"[~{getattr(issue.fields.reporter, 'accountId', '')}]" if hasattr(issue.fields, "reporter") and getattr(issue.fields.reporter, "accountId", None) else reporter_name

                    prompt = (
                        "Вы — технический лидер (Tech Lead). "
                        f"Напишите короткое, вежливое сообщение автору ({reporter_name}) задачи Jira ({issue.key}), "
                        "которая находится в статусе Resolved уже 3 дня, но не была проверена и закрыта. "
                        f"Попросите его ({reporter_name}) проверить и закрыть задачу (статус Closed/Done), или вернуть в работу. "
                        "Сообщение должно быть на русском языке. "
                        f"В сообщение добавьте упоминание: {reporter_mention}"
                    )

                    response = await llm.ainvoke([HumanMessage(content=prompt)])
                    comment_body = f"{response.content}\n\n{reminder_marker}"
                    jira_client.add_comment(issue.key, comment_body)
                    logger.info(f"Posted inactive reporter reminder on issue {issue.key}.")
            except Exception as e:
                logger.error(f"Error processing inactive reporter reminder for issue {issue.key}: {e}")

    return "Jira inactive reporter reminder task complete."

async def jira_blocked_task_alert_task():
    """
    Checks Jira tasks in active sprints that have been in 'Blocked' status for more than 2 days,
    and posts a comment tagging the Scrum Master or Tech Lead for assistance.
    """
    import logging
    from langchain_core.messages import HumanMessage


    logger = logging.getLogger(__name__)
    logger.info("Starting automated Jira blocked task alert task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping Jira blocked task alert.")
        return "Jira blocked task alert task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    jira_client = JiraClient()
    tracked_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_JIRA_BLOCKED_TASK_ALERT -->"

    for project_key in tracked_projects:
        jql = f'project = "{project_key}" AND sprint in openSprints() AND status = "Blocked" AND updated <= -2d'
        issues = jira_client.search_issues(jql)
        logger.info(f"Found {len(issues)} blocked issues inactive for 2 days in active sprint in project {project_key}")

        for issue in issues:
            try:
                comments = jira_client.get_comments(issue.key)
                already_reminded = any(reminder_marker in getattr(c, "body", "") for c in comments)

                if not already_reminded:
                    prompt = (
                        "Вы — автоматический помощник. "
                        f"Напишите короткое сообщение для задачи Jira ({issue.key}), "
                        "которая находится в статусе Blocked более 2 дней в активном спринте. "
                        "Попросите Scrum Master или Tech Lead обратить внимание и помочь разблокировать задачу. "
                        "Сообщение должно быть на русском языке. "
                        "Упомяните, что задаче требуется помощь для разблокировки."
                    )

                    response = await llm.ainvoke([HumanMessage(content=prompt)])
                    comment_body = f"{response.content}\n\n{reminder_marker}"
                    jira_client.add_comment(issue.key, comment_body)
                    logger.info(f"Posted blocked task alert on issue {issue.key}.")
            except Exception as e:
                logger.error(f"Error processing blocked task alert for issue {issue.key}: {e}")

    return "Jira blocked task alert task complete."

async def gitlab_mr_approval_reminder_task():
    """
    Checks non-draft MRs that have been open for > 2 days, have no unresolved threads,
    have passing pipelines, but are lacking approvals, and reminds the reviewers.
    """
    import logging
    from datetime import datetime, timezone
    import dateutil.parser

    logger = logging.getLogger(__name__)
    logger.info("Starting automated GitLab MR approval reminder task...")

    gitlab_client = GitLabClient()
    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_GITLAB_MR_APPROVAL_REMINDER -->"
    now = datetime.now(timezone.utc)

    for pid in tracked_projects:
        try:
            mrs = gitlab_client.get_merge_requests(pid, state="opened")
        except Exception as e:
            logger.error(f"Failed to fetch MRs for project {pid}: {e}")
            continue

        for mr in mrs:
            if getattr(mr, 'draft', False):
                continue

            created_at_str = getattr(mr, "created_at", None)
            if not created_at_str:
                continue

            created_at = dateutil.parser.isoparse(created_at_str)
            if (now - created_at).days <= 2:
                continue

            if mr.has_conflicts:
                continue

            try:
                # check pipelines
                pipelines = mr.pipelines.list(per_page=1)
                if not pipelines or pipelines[0].status != "success":
                    continue
            except Exception:
                continue

            try:
                discussions = mr.discussions.list(all=True)
                has_unresolved = any(
                    any(note.get('resolvable') and not note.get('resolved') for note in d.attributes.get('notes', []))
                    for d in discussions
                )
                if has_unresolved:
                    continue
            except Exception:
                pass

            try:
                approvals = mr.approvals.get()
                if approvals.approved_by:
                    continue
            except Exception:
                pass

            try:
                notes = mr.notes.list(all=True)
                already_reminded = any(reminder_marker in (getattr(n, "body", "") or "") for n in notes)
                if already_reminded:
                    continue
            except Exception:
                pass

            reviewers = [r.get("username", "") for r in getattr(mr, "reviewers", []) if r.get("username")]
            tags = " ".join([f"@{r}" for r in reviewers]) if reviewers else ""

            body = (
                f"{reminder_marker}\n"
                f"Привет! {tags}\n"
                f"Этот MR открыт уже более 2 дней, пайплайны успешны и нет неразрешенных обсуждений. "
                f"Пожалуйста, посмотрите и заапрувьте, если все ок!"
            )
            try:
                gitlab_client.create_mr_note(pid, mr.iid, body)
                logger.info(f"Posted approval reminder for MR !{mr.iid} in project {pid}.")
            except Exception as e:
                logger.error(f"Failed to post approval reminder for MR !{mr.iid}: {e}")

    return "GitLab MR approval reminder task completed."

async def jira_missing_epic_reminder_task():
    """
    Checks Jira tasks (except Sub-tasks and Epics) in active sprints that do not have an Epic Link,
    and asks the author to add one.
    """
    import logging
    from langchain_core.messages import HumanMessage

    logger = logging.getLogger(__name__)
    logger.info("Starting automated Jira missing epic link reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping Jira missing epic link reminder.")
        return "Jira missing epic reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    jira_client = JiraClient()
    tracked_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_JIRA_MISSING_EPIC_REMINDER -->"

    for j_proj in tracked_projects:
        try:
            sprints = jira_client.get_project_sprints(j_proj)
            active_sprints = [s for s in sprints if s.get("state") == "active"]
            if not active_sprints:
                continue

            for sprint in active_sprints:
                issues = jira_client.get_sprint_issues(sprint["id"])
                for issue in issues:
                    issue_type = issue.get("fields", {}).get("issuetype", {}).get("name", "")
                    if issue_type in ["Epic", "Sub-task"]:
                        continue

                    # Epic Link field is usually customfield_10014 or similar.
                    # Or 'parent' for next-gen projects.
                    fields = issue.get("fields", {})
                    epic_link = fields.get("customfield_10014") or fields.get("parent")
                    if epic_link:
                        continue

                    issue_key = issue.get("key")
                    reporter = fields.get("reporter", {})
                    reporter_account_id = reporter.get("accountId")

                    if not reporter_account_id:
                        continue

                    comments = jira_client.get_issue_comments(issue_key)
                    already_reminded = any(reminder_marker in c.get("body", "") for c in comments)

                    if already_reminded:
                        continue

                    prompt = (
                        f"Ты ассистент, который пишет вежливое напоминание в Jira на русском языке. "
                        f"Задача (кроме Epic и Sub-task) не привязана к Epic. "
                        f"Упомяни [~accountid:{reporter_account_id}], чтобы он привязал задачу к соответствующему Epic, так как это важно для отслеживания релизов и фич. "
                        f"Верни только текст комментария, без кавычек и дополнительных пояснений."
                    )

                    try:
                        resp = await llm.ainvoke([HumanMessage(content=prompt)])
                        comment_text = f"{reminder_marker}\n{resp.content.strip()}"
                        jira_client.add_issue_comment(issue_key, comment_text)
                        logger.info(f"Posted missing epic reminder for Jira issue {issue_key}.")
                    except Exception as e:
                        logger.error(f"Failed to process missing epic reminder for Jira issue {issue_key}: {e}")

        except Exception as e:
            logger.error(f"Failed to process Jira missing epic reminder for project {j_proj}: {e}")

    return "Jira missing epic reminder task completed."

async def jira_high_complexity_warning_task():
    """
    Checks Jira tasks with high story point estimations (>= 13)
    and suggests breaking them down into sub-tasks.
    """
    import logging
    from langchain_core.messages import HumanMessage

    logger = logging.getLogger(__name__)
    logger.info("Starting automated Jira high complexity warning task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping Jira high complexity warning.")
        return "Jira high complexity warning task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    jira_client = JiraClient()
    tracked_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]
    story_points_field = settings.get("JIRA_STORY_POINTS_FIELD", "customfield_10016")

    reminder_marker = "<!-- AUTO_GENERATED_JIRA_HIGH_COMPLEXITY_WARNING -->"

    for j_proj in tracked_projects:
        try:
            sprints = jira_client.get_project_sprints(j_proj)
            active_sprints = [s for s in sprints if s.get("state") == "active"]
            if not active_sprints:
                continue

            for sprint in active_sprints:
                issues = jira_client.get_sprint_issues(sprint["id"])
                for issue in issues:
                    fields = issue.get("fields", {})
                    issue_type = fields.get("issuetype", {}).get("name", "")
                    if issue_type in ["Epic"]:
                        continue

                    sp = fields.get(story_points_field)
                    try:
                        sp_val = float(sp)
                    except (TypeError, ValueError):
                        sp_val = 0

                    if sp_val < 13:
                        continue

                    issue_key = issue.get("key")
                    reporter = fields.get("reporter", {})
                    reporter_account_id = reporter.get("accountId")

                    if not reporter_account_id:
                        continue

                    comments = jira_client.get_issue_comments(issue_key)
                    already_reminded = any(reminder_marker in c.get("body", "") for c in comments)

                    if already_reminded:
                        continue

                    prompt = (
                        f"Ты Scrum Master, пишущий комментарий в Jira на русском языке. "
                        f"У этой задачи высокая оценка ({sp_val} Story Points). "
                        f"Упомяни [~accountid:{reporter_account_id}] и предложи декомпозировать задачу на подзадачи (Sub-tasks), чтобы ее было легче оценить и выполнить. "
                        f"Верни только текст комментария, без кавычек и дополнительных пояснений."
                    )

                    try:
                        resp = await llm.ainvoke([HumanMessage(content=prompt)])
                        comment_text = f"{reminder_marker}\n{resp.content.strip()}"
                        jira_client.add_issue_comment(issue_key, comment_text)
                        logger.info(f"Posted high complexity warning for Jira issue {issue_key}.")
                    except Exception as e:
                        logger.error(f"Failed to process high complexity warning for Jira issue {issue_key}: {e}")

        except Exception as e:
            logger.error(f"Failed to process Jira high complexity warning for project {j_proj}: {e}")

    return "Jira high complexity warning task completed."


async def gitlab_mr_missing_assignee_notifier_task():
    """
    Iterates through opened MRs, checks if assignee is missing. If so, uses LLM to generate a reminder text
    and posts it via create_mr_note.
    """
    import logging
    from langchain_core.messages import HumanMessage
    global GitLabClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting automated GitLab MR missing assignee notifier task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping MR missing assignee notifier.")
        return "GitLab MR missing assignee notifier task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    gitlab_client = GitLabClient()
    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_MR_MISSING_ASSIGNEE_NOTIFIER -->"

    for project_id in tracked_projects:
        try:
            mrs = gitlab_client.get_project_merge_requests(project_id, state="opened")
            for mr in mrs:
                try:
                    if getattr(mr, 'assignee', None):
                        continue

                    # Also check if it's draft, sometimes we don't want to bother if it's draft
                    if getattr(mr, 'draft', False) or getattr(mr, 'title', '').lower().startswith("draft:"):
                        continue

                    notes = mr.notes.list(all=True)
                    already_reminded = any(reminder_marker in note.body for note in notes)

                    if not already_reminded:
                        author_name = getattr(getattr(mr, 'author', None), 'username', 'Author')
                        prompt = (
                            f"Ты - вежливый технический помощник. Напиши очень короткий комментарий (на русском языке) "
                            f"для автора Merge Request (упомяни @{author_name}), в котором скажи, что в этом MR "
                            f"({mr.title}) не указан assignee (ответственный), и попроси его назначить. "
                            f"Без приветствий, просто текст напоминания."
                        )
                        resp = await llm.ainvoke([HumanMessage(content=prompt)])
                        comment_text = f"{reminder_marker}\n{resp.content.strip()}"

                        gitlab_client.create_mr_note(project_id, mr.iid, comment_text)
                        logger.info(f"Posted missing assignee reminder for MR !{mr.iid} in project {project_id}.")

                except Exception as e:
                    logger.error(f"Error processing missing assignee for MR !{getattr(mr, 'iid', 'unknown')} in project {project_id}: {e}")

        except Exception as e:
            logger.error(f"Error processing MR missing assignee for GitLab project {project_id}: {e}")

    return "GitLab MR missing assignee notifier task completed."

async def jira_missing_labels_reminder_task():
    """
    Checks Jira tasks in active sprints that lack labels and prompts the team to add them.
    """
    import logging
    from langchain_core.messages import HumanMessage
    global JiraClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting automated Jira missing labels reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping Jira missing labels reminder.")
        return "Jira missing labels reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    jira_client = JiraClient()
    tracked_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_JIRA_MISSING_LABELS_REMINDER -->"

    for project_key in tracked_projects:
        try:
            jql = f'project = "{project_key}" AND sprint in openSprints()'
            issues = jira_client.search_issues(jql)

            for issue in issues:
                labels = getattr(issue.fields, "labels", [])
                if labels:
                    continue

                comments = jira_client.get_comments(issue.key)
                already_reminded = any(reminder_marker in getattr(c, "body", "") for c in comments)

                if already_reminded:
                    continue

                reporter_name = getattr(issue.fields.reporter, "displayName", "Reporter") if hasattr(issue.fields, "reporter") and issue.fields.reporter else "Reporter"
                reporter_mention = f"[~{getattr(issue.fields.reporter, 'accountId', '')}]" if hasattr(issue.fields, "reporter") and getattr(issue.fields.reporter, "accountId", None) else reporter_name

                prompt = (
                    f"Ты - вежливый Scrum Master. Напиши короткий комментарий (на русском языке) для "
                    f"задачи {issue.key}. Упомяни {reporter_mention} и напомни, что в задаче не проставлены метки (labels), "
                    f"и попроси их добавить для лучшей категоризации и отслеживания. "
                    f"Без приветствий, просто текст напоминания."
                )
                resp = await llm.ainvoke([HumanMessage(content=prompt)])
                comment_text = f"{reminder_marker}\n{resp.content.strip()}"

                jira_client.add_comment(issue.key, comment_text)
                logger.info(f"Posted missing labels reminder for Jira issue {issue.key}.")

        except Exception as e:
            logger.error(f"Error processing missing labels for project {project_key}: {e}")

    return "Jira missing labels reminder task completed."

async def gitlab_stale_draft_mr_closer_task():
    """
    Closes Draft MRs that have been inactive for over 30 days.
    """
    import logging
    from datetime import datetime, timezone
    global GitLabClient
    from app.clients import settings

    logger = logging.getLogger(__name__)
    logger.info("Starting automated GitLab stale draft MR closer task...")

    gitlab_client = GitLabClient()
    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    now = datetime.now(timezone.utc)
    reminder_marker = "<!-- AUTO_GENERATED_STALE_DRAFT_MR_CLOSER -->"

    for project_id in tracked_projects:
        try:
            gl_project = gitlab_client.get_project(project_id)
            if not gl_project:
                continue

            mrs = gitlab_client.get_project_merge_requests(project_id, state="opened")
            for mr in mrs:
                try:
                    if not (getattr(mr, 'draft', False) or getattr(mr, 'title', '').lower().startswith("draft:")):
                        continue

                    updated_at_str = getattr(mr, "updated_at", None)
                    if not updated_at_str:
                        continue

                    # Handle python < 3.11 fromisoformat 'Z' issue
                    if updated_at_str.endswith('Z'):
                        updated_at_str = updated_at_str[:-1] + '+00:00'
                    updated_at = datetime.fromisoformat(updated_at_str)

                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)

                    days_inactive = (now - updated_at).days
                    if days_inactive > 30:
                        # Fetch the full object to ensure we can edit and save
                        full_mr = gl_project.mergerequests.get(mr.iid)

                        full_mr.state_event = 'close'
                        full_mr.save()

                        comment_text = (
                            f"{reminder_marker}\n"
                            f"Этот Draft Merge Request не обновлялся более 30 дней, поэтому он был автоматически закрыт. "
                            f"Вы можете открыть его снова (Reopen), когда будете готовы продолжить работу."
                        )
                        gitlab_client.create_mr_note(project_id, mr.iid, comment_text)
                        logger.info(f"Closed stale Draft MR !{mr.iid} in project {project_id}.")

                except Exception as e:
                    logger.error(f"Error processing stale draft closer for MR !{getattr(mr, 'iid', 'unknown')} in project {project_id}: {e}")

        except Exception as e:
            logger.error(f"Error processing MR stale draft closer for GitLab project {project_id}: {e}")

    return "GitLab stale draft MR closer task completed."
async def gitlab_mr_missing_milestone_notifier_task():
    """
    Iterates over open MRs for tracked projects.
    If an MR has no milestone, checks if a reminder has been sent.
    If not, generates a polite notification via LLM in Russian asking to add a milestone.
    """
    import logging
    # Use global imports so mocker can patch them in app.tasks
    global GitLabClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting GitLab missing milestone notifier task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping missing milestone notifier.")
        return "GitLab missing milestone notifier task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)

    gitlab_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    gitlab_projects = [p.strip() for p in gitlab_projects if p.strip()]

    client = GitLabClient()
    reminder_marker = "<!-- AUTO_GENERATED_MISSING_MILESTONE_NOTIFIER -->"

    for project_id in gitlab_projects:
        try:
            project = client.client.projects.get(project_id)
            mrs = project.mergerequests.list(state='opened', get_all=True)

            for mr in mrs:
                if mr.milestone is None:
                    mr_notes = mr.notes.list(get_all=True)
                    already_notified = any(reminder_marker in note.body for note in mr_notes)

                    if not already_notified:
                        messages = [
                            SystemMessage(
                                content="Ты — помощник техлида. Твоя задача — вежливо напомнить разработчику о необходимости указать майлстоун (milestone) в GitLab Merge Request. "
                                        "Напиши короткое, дружелюбное сообщение на русском языке."
                            ),
                            HumanMessage(content=f"Напиши комментарий для Merge Request '{mr.title}', в котором нет майлстоуна.")
                        ]
                        response = await llm.ainvoke(messages)
                        comment_body = f"{reminder_marker}\n{response.content}"

                        client.create_mr_note(project_id, mr.iid, comment_body)
                        logger.info(f"Posted missing milestone reminder for MR !{mr.iid} in project {project_id}.")
        except Exception as e:
            logger.error(f"Error processing missing milestone notifier for GitLab project {project_id}: {e}")

    return "GitLab missing milestone notifier task completed."

async def jira_large_story_decomposition_reminder_task():
    """
    Checks Jira tasks that have > 8 story points but no subtasks, and suggests decomposition.
    """
    import logging
    from langchain_core.messages import HumanMessage, SystemMessage
    global JiraClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting automated Jira large story decomposition reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping Jira large story decomposition reminder.")
        return "Jira large story decomposition reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    jira_client = JiraClient()
    tracked_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]
    story_points_field = settings.get("JIRA_STORY_POINTS_FIELD", "customfield_10016")

    reminder_marker = "<!-- AUTO_GENERATED_JIRA_LARGE_STORY_DECOMPOSITION_REMINDER -->"

    for project_key in tracked_projects:
        try:
            # Skip Epics and Sub-tasks
            jql = f'project = "{project_key}" AND statusCategory != Done AND issuetype not in (Epic, Sub-task)'
            issues = jira_client.search_issues(jql)

            for issue in issues:
                story_points = getattr(issue.fields, story_points_field, None)
                try:
                    if story_points is None:
                        continue
                    sp_value = float(story_points)
                    if sp_value <= 8.0:
                        continue
                except ValueError:
                    continue

                subtasks = getattr(issue.fields, "subtasks", [])
                if subtasks and len(subtasks) > 0:
                    continue

                comments = jira_client.get_comments(issue.key)
                already_reminded = any(reminder_marker in getattr(c, "body", "") for c in comments)

                if already_reminded:
                    continue

                assignee_name = getattr(issue.fields.assignee, "displayName", "Assignee") if hasattr(issue.fields, "assignee") and issue.fields.assignee else "Assignee"
                assignee_mention = f"[~{getattr(issue.fields.assignee, 'accountId', '')}]" if hasattr(issue.fields, "assignee") and getattr(issue.fields.assignee, "accountId", None) else assignee_name

                prompt = (
                    f"Ты - Agile Coach. Напиши вежливый комментарий (на русском языке) для "
                    f"задачи {issue.key}. Упомяни {assignee_mention} и порекомендуй декомпозировать задачу на подзадачи (sub-tasks), "
                    f"так как её оценка составляет {sp_value} Story Points, что является довольно большим размером для одной задачи без подзадач. "
                    f"Без приветствий, просто текст."
                )

                resp = await llm.ainvoke([
                    SystemMessage(content="Ты — технический ассистент, помогающий командам соблюдать agile-практики."),
                    HumanMessage(content=prompt)
                ])
                comment_text = f"{reminder_marker}\n{resp.content.strip()}"

                jira_client.add_comment(issue.key, comment_text)
                logger.info(f"Posted large story decomposition reminder for Jira issue {issue.key}.")

        except Exception as e:
            logger.error(f"Error processing large story decomposition for project {project_key}: {e}")

    return "Jira large story decomposition reminder task completed."


async def jira_high_priority_out_of_sprint_reminder_task():
    """
    Checks for Jira tasks with 'Highest' priority that are not in an active sprint
    and notifies the assignee to plan them into a sprint or adjust priority.
    """
    import logging
    from langchain_core.messages import HumanMessage, SystemMessage
    global JiraClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting automated Jira high priority out of sprint reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping Jira high priority out of sprint reminder.")
        return "Jira high priority out of sprint reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    jira_client = JiraClient()
    tracked_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_JIRA_HIGH_PRIORITY_OUT_OF_SPRINT_REMINDER -->"

    for project_key in tracked_projects:
        try:
            # Query for Highest priority tasks not in an active sprint and not done
            jql = f'project = "{project_key}" AND priority = Highest AND (sprint is EMPTY OR sprint not in openSprints()) AND statusCategory != Done'
            issues = jira_client.search_issues(jql)

            for issue in issues:
                comments = jira_client.get_comments(issue.key)
                already_reminded = any(reminder_marker in getattr(c, "body", "") for c in comments)
                if already_reminded:
                    continue

                assignee = getattr(issue.fields, "assignee", None)
                assignee_mention = f"[~accountid:{assignee.accountId}]" if assignee and hasattr(assignee, "accountId") else "Команда"

                prompt = (
                    f"Ты - Agile Coach. Напиши вежливый комментарий (на русском языке) для "
                    f"задачи {issue.key}. Упомяни {assignee_mention} и обрати внимание, что задача имеет наивысший приоритет (Highest), "
                    f"но не находится в активном спринте. Предложи взять ее в работу в текущем спринте или понизить приоритет, если она сейчас не актуальна. "
                    f"Без приветствий, просто текст."
                )

                resp = await llm.ainvoke([
                    SystemMessage(content="Ты — технический ассистент, помогающий командам соблюдать agile-практики."),
                    HumanMessage(content=prompt)
                ])
                comment_text = f"{reminder_marker}\n{resp.content.strip()}"

                jira_client.add_comment(issue.key, comment_text)
                logger.info(f"Posted high priority out of sprint reminder for Jira issue {issue.key}.")

        except Exception as e:
            logger.error(f"Error processing high priority out of sprint reminder for project {project_key}: {e}")

    return "Jira high priority out of sprint reminder task completed."


async def gitlab_mr_description_checklist_validator_task():
    """
    Checks if open MRs contain a checklist in their description (either [ ] or [x]).
    If not, posts a reminder to add a verification checklist.
    """
    import logging
    from langchain_core.messages import HumanMessage, SystemMessage
    global GitLabClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting automated GitLab MR description checklist validator task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping GitLab MR checklist validator.")
        return "GitLab MR description checklist validator task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    gitlab_client = GitLabClient()
    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_GITLAB_MR_CHECKLIST_VALIDATOR -->"

    for gl_proj in tracked_projects:
        try:
            mrs = gitlab_client.get_project_mrs(gl_proj, state="opened")
            for mr_data in mrs:
                description = mr_data.get("description") or ""
                # Check for Markdown checklist items
                if "[ ]" in description or "[x]" in description.lower() or "[X]" in description:
                    continue

                mr_iid = mr_data.get("iid")
                notes = gitlab_client.get_mr_notes(gl_proj, mr_iid)
                already_reminded = any(reminder_marker in getattr(n, "body", "") for n in notes)

                if already_reminded:
                    continue

                author = mr_data.get("author", {})
                author_username = author.get("username", "")
                mention = f"@{author_username}" if author_username else "Автор"

                prompt = (
                    f"Ты - Quality Assurance Lead. Напиши вежливый комментарий (на русском языке) для "
                    f"Merge Request !{mr_iid}. Упомяни {mention} и обрати внимание, что в описании MR отсутствует "
                    f"чек-лист для проверки (markdown формат [ ]). Попроси добавить чек-лист того, что нужно протестировать или проверить перед мержем. "
                    f"Без приветствий, просто текст."
                )

                resp = await llm.ainvoke([
                    SystemMessage(content="Ты — технический ассистент, помогающий командам соблюдать процессы разработки и тестирования."),
                    HumanMessage(content=prompt)
                ])
                comment_text = f"{reminder_marker}\n{resp.content.strip()}"

                gitlab_client.create_mr_note(gl_proj, mr_iid, comment_text)
                logger.info(f"Posted missing checklist reminder for GitLab MR !{mr_iid} in project {gl_proj}.")

        except Exception as e:
            logger.error(f"Failed to process GitLab MR checklist validator for project {gl_proj}: {e}")

    return "GitLab MR description checklist validator task completed."


async def gitlab_mr_code_churn_notifier_task():
    """Alerts when an MR introduces significant code churn > 1000 lines."""
    logger.info("Running GitLab Code Churn Alert task.")

    gitlab_client = GitLabClient()
    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")

    if not tracked_projects or tracked_projects == [""]:
        return "Code churn alert task skipped (no projects tracked)"

    threshold = 1000

    for project_id in tracked_projects:
        project_id = project_id.strip()
        if not project_id:
            continue

        try:
            mrs = gitlab_client.client.projects.get(project_id).mergerequests.list(state='opened', get_all=True)
            for mr in mrs:
                try:
                    changes = mr.changes()

                    churn = 0
                    if changes and "changes" in changes:
                        for change in changes["changes"]:
                            diff = change.get("diff", "")
                            # Count lines starting with + or - (but not +++ or ---)
                            lines = diff.split('\n')
                            for line in lines:
                                if line.startswith('+') and not line.startswith('+++'):
                                    churn += 1
                                elif line.startswith('-') and not line.startswith('---'):
                                    churn += 1

                    if churn > threshold:
                        # Check labels
                        labels = mr.labels
                        if "high-churn" not in labels:
                            labels.append("high-churn")
                            gitlab_client.update_mr_labels(project_id, mr.iid, labels)

                        # Check comments to prevent duplicates
                        notes = mr.notes.list(all=True)
                        marker = "<!-- AUTO_GENERATED_CHURN_ALERT -->"
                        already_commented = any(marker in getattr(n, 'body', '') for n in notes)

                        if not already_commented:
                            body = f"{marker}\n**Code Churn Alert**: This MR introduces significant code churn ({churn} additions/deletions). Please consider breaking it down into smaller, more manageable MRs to ease review."
                            gitlab_client.create_mr_note(project_id, mr.iid, body)

                except Exception as e:
                    logger.error(f"Error checking churn for MR {mr.iid} in project {project_id}: {e}")
        except Exception as e:
            logger.error(f"Error checking open MRs for project {project_id}: {e}")

    return "Code churn alert task completed"

async def jira_stale_epic_reminder_task():
    """
    Checks for Jira Epics that have not been updated for 30 days and are not in 'Done' status.
    Generates an automated reminder using LLM to update or close the epic.
    """
    import logging
    from langchain_core.messages import HumanMessage, SystemMessage
    global JiraClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting automated Jira stale epic reminder task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping Jira stale epic reminder.")
        return "Jira stale epic reminder task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    jira_client = JiraClient()
    tracked_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_JIRA_STALE_EPIC_REMINDER -->"

    for project_key in tracked_projects:
        try:
            # Query for Epics not updated in 30 days and not Done
            jql = f'project = "{project_key}" AND issuetype = Epic AND statusCategory != Done AND updated <= -30d'
            issues = jira_client.search_issues(jql)

            for issue in issues:
                comments = jira_client.get_comments(issue.key)
                already_reminded = any(reminder_marker in getattr(c, "body", "") for c in comments)
                if already_reminded:
                    continue

                assignee = getattr(issue.fields, "assignee", None)
                assignee_mention = f"[~accountid:{assignee.accountId}]" if assignee and hasattr(assignee, "accountId") else "Команда"

                prompt = (
                    f"Ты - Agile Coach. Напиши вежливый комментарий (на русском языке) для "
                    f"Эпика {issue.key}. Упомяни {assignee_mention} и обрати внимание, что этот эпик не обновлялся "
                    f"уже более 30 дней. Предложи актуализировать статус, добавить комментарий о прогрессе или закрыть его, если он больше не актуален. "
                    f"Без приветствий, просто текст."
                )

                resp = await llm.ainvoke([
                    SystemMessage(content="Ты — технический ассистент, помогающий командам соблюдать agile-практики."),
                    HumanMessage(content=prompt)
                ])
                comment_text = f"{reminder_marker}\n{resp.content.strip()}"

                jira_client.add_comment(issue.key, comment_text)
                logger.info(f"Posted stale epic reminder for Jira issue {issue.key}.")

        except Exception as e:
            logger.error(f"Error processing stale epic reminder for project {project_key}: {e}")

    return "Jira stale epic reminder task completed."
async def gitlab_mr_missing_labels_notifier_task():
    """
    Checks tracked GitLab projects for open Merge Requests that have no labels.
    If no labels are found, generates an automated message asking the author to add labels.
    """
    import logging
    from langchain_core.messages import HumanMessage

    logger = logging.getLogger(__name__)
    logger.info("Starting GitLab MR missing labels notifier task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping GitLab MR missing labels notifier.")
        return "GitLab MR missing labels notifier task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    gitlab_client = GitLabClient()
    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_GITLAB_MISSING_LABELS_REMINDER -->"

    for project_id in tracked_projects:
        try:
            project = gitlab_client.client.projects.get(project_id)
            mrs = project.mergerequests.list(state="opened", all=True)

            for mr in mrs:
                try:
                    labels = list(getattr(mr, "labels", []))
                    if not labels:
                        # Check if we already posted a reminder
                        notes = mr.notes.list(all=True)
                        already_notified = any(reminder_marker in note.body for note in notes)

                        if not already_notified:
                            author_username = mr.author.get("username", "author") if hasattr(mr, "author") and isinstance(mr.author, dict) else "author"
                            author_mention = f"@{author_username}"

                            prompt = (
                                f"Напиши короткое, вежливое сообщение (2-3 предложения) для автора Merge Request {mr.iid}, "
                                f"упомянув его ({author_mention}). Напомни, что в MR отсутствуют метки (labels), "
                                "и попроси добавить подходящие метки для правильной категоризации. "
                                "Пиши на русском языке без приветствия."
                            )
                            response = await llm.ainvoke([HumanMessage(content=prompt)])
                            comment_body = f"{response.content}\n\n{reminder_marker}"

                            gitlab_client.create_mr_note(project_id, mr.iid, comment_body)
                            logger.info(f"Posted missing labels reminder for MR {mr.iid} in project {project_id}.")
                except Exception as e:
                    logger.error(f"Error processing MR {mr.iid} in project {project_id} for missing labels notifier: {e}")
        except Exception as e:
            logger.error(f"Error processing missing labels notifier for project {project_id}: {e}")

    return "GitLab MR missing labels notifier task completed."


async def confluence_author_summary_task():
    """
    Generates a periodic summary of recently contributed Confluence pages grouped by author.
    Generates an HTML report in Russian via LLM and publishes it to Confluence.
    """
    from app.clients import settings
    from app.clients.confluence_client import ConfluenceClient
    from langchain_openai import ChatOpenAI
    import logging
    from langchain_core.messages import HumanMessage
    from datetime import datetime, timezone, timedelta
    from collections import defaultdict

    logger = logging.getLogger(__name__)
    logger.info("Starting Confluence author summary task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping Confluence author summary.")
        return "Confluence author summary task skipped (no OpenAI API key)"

    tracked_spaces = settings.get("CONFLUENCE_TRACKED_SPACES", "").split(",")
    tracked_spaces = [s.strip() for s in tracked_spaces if s.strip()]

    if not tracked_spaces:
        logger.info("No CONFLUENCE_TRACKED_SPACES configured. Skipping task.")
        return "Confluence author summary task skipped (no spaces configured)"

    space = tracked_spaces[0]

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    confluence_client = ConfluenceClient()

    # Get recent pages (e.g., from the last 7 days)
    now = datetime.now(timezone.utc)
    one_week_ago = now - timedelta(days=7)

    author_pages = defaultdict(list)

    try:
        pages_response = confluence_client.client.get_all_pages_from_space(space, expand="version,history.lastUpdated", start=0, limit=100)
        pages = []
        if isinstance(pages_response, list):
            pages = pages_response
        elif isinstance(pages_response, dict) and "results" in pages_response:
            pages = pages_response["results"]

        for page in pages:
            version_info = page.get("version", {})
            when_str = version_info.get("when")
            if when_str:
                try:
                    # Parse Confluence date, e.g. "2023-10-10T12:00:00.000+0000"
                    when_dt = datetime.strptime(when_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                    if when_dt >= one_week_ago:
                        by = version_info.get("by", {})
                        author_name = by.get("displayName") or by.get("username") or "Unknown Author"
                        title = page.get("title", "Untitled")
                        # You could also gather the link here
                        base_url = confluence_client.client.url
                        link = f"{base_url}/spaces/{space}/pages/{page.get('id')}"
                        author_pages[author_name].append({"title": title, "link": link})
                except Exception as e:
                    logger.error(f"Error parsing date {when_str}: {e}")
                    pass

    except Exception as e:
        logger.error(f"Error fetching pages for space {space}: {e}")
        return f"Confluence author summary task failed: {e}"

    if not author_pages:
        logger.info("No recent contributions found.")
        return "Confluence author summary task completed (no recent contributions)"

    # Build context for LLM
    context_lines = []
    for author, pages in author_pages.items():
        context_lines.append(f"Автор: {author}")
        for p in pages:
            context_lines.append(f" - Страница: {p['title']} ({p['link']})")
        context_lines.append("")

    context_text = "\n".join(context_lines)

    prompt = (
        f"Сгенерируй красивый HTML-отчет (без тегов <html> или markdown блоков, только содержимое) "
        f"на русском языке, summarizing недавние обновления страниц Confluence по авторам.\n\n"
        f"Данные:\n{context_text}\n\n"
        f"Отчет должен быть структурированным, дружелюбным и поощрять авторов за их вклад."
    )

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        html_content = response.content.strip()

        # Clean up markdown if llm included it
        if html_content.startswith("```html"):
            html_content = html_content[7:]
            if html_content.endswith("```"):
                html_content = html_content[:-3]

        title = f"Сводка активности авторов: {datetime.now().strftime('%Y-%m-%d')}"

        confluence_client.client.create_page(
            space=space,
            title=title,
            body=html_content.strip(),
            parent_id=None
        )
        logger.info(f"Published Confluence author summary to space {space}.")
    except Exception as e:
        logger.error(f"Failed to generate or publish Confluence author summary: {e}")
        return f"Confluence author summary task failed: {e}"

    return "Confluence author summary task completed"

async def confluence_stale_page_reminder_task():
    """
    Checks tracked Confluence spaces for pages that haven't been updated in over 180 days.
    If a page is stale, it adds an automated comment asking the author to verify its relevance.
    """
    import logging
    from datetime import datetime, timezone, timedelta
    from langchain_core.messages import HumanMessage
    from app.clients.confluence_client import ConfluenceClient
    from app.clients import settings
    from langchain_openai import ChatOpenAI

    logger = logging.getLogger(__name__)
    logger.info("Starting Confluence stale page reminder task...")

    if not settings.get("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not found. Skipping Confluence stale page reminder.")
        return "Confluence stale page reminder task skipped (no OpenAI API key)"

    tracked_spaces = settings.get("CONFLUENCE_TRACKED_SPACES", "").split(",")
    if not tracked_spaces or not tracked_spaces[0].strip():
        logger.info("No CONFLUENCE_TRACKED_SPACES configured. Skipping task.")
        return "Confluence stale page reminder task skipped (no spaces configured)"

    confluence_client = ConfluenceClient()
    marker = "<!-- AUTO_GENERATED_CONFLUENCE_STALE_PAGE_REMINDER -->"
    stale_threshold = datetime.now(timezone.utc) - timedelta(days=180)
    llm = ChatOpenAI(temperature=0.7, model="gpt-4o")

    for space in tracked_spaces:
        space = space.strip()
        if not space:
            continue
        try:
            pages_response = confluence_client.client.get_all_pages_from_space(space, expand="version,history.lastUpdated", start=0, limit=100)
            pages = []
            if isinstance(pages_response, list):
                pages = pages_response
            elif isinstance(pages_response, dict) and "results" in pages_response:
                pages = pages_response["results"]

            for page in pages:
                version_info = page.get("version", {})
                when_str = version_info.get("when")
                if when_str:
                    try:
                        when_dt = datetime.strptime(when_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                        if when_dt < stale_threshold:
                            page_id = page.get("id")
                            title = page.get("title", "Untitled")

                            # Check existing comments
                            comments_response = confluence_client.client.get_page_comments(page_id, expand="body.storage")
                            comments = []
                            if isinstance(comments_response, dict) and "results" in comments_response:
                                comments = comments_response["results"]
                            elif isinstance(comments_response, list):
                                comments = comments_response

                            already_reminded = False
                            for comment in comments:
                                body = comment.get("body", {}).get("storage", {}).get("value", "")
                                if marker in body:
                                    already_reminded = True
                                    break

                            if not already_reminded:
                                prompt = (
                                    f"Сгенерируй короткое и вежливое напоминание (в 1-2 предложениях) автору страницы в Confluence '{title}', "
                                    "о том, что страница не обновлялась более полугода. Попроси проверить её актуальность и обновить или заархивировать, если она устарела. "
                                    "Не используй Markdown форматирование. Пиши просто текст."
                                )
                                response = await llm.ainvoke([HumanMessage(content=prompt)])

                                comment_body = f"{marker}\n{response.content}"
                                confluence_client.client.add_comment(page_id, comment_body)
                                logger.info(f"Added stale reminder to Confluence page '{title}' ({page_id}).")

                    except Exception as e:
                        logger.error(f"Error parsing date or adding comment for page {page.get('id')}: {e}")

        except Exception as e:
            logger.error(f"Error processing Confluence space {space} for stale pages: {e}")

    return "Confluence stale page reminder task completed."


async def confluence_stale_architecture_review_reminder_task():
    """
    Checks tracked Confluence spaces for architecture documents (pages with label 'architecture' or 'arch')
    that haven't been reviewed/updated in over 180 days.
    If an architecture document is stale, it adds an automated comment asking the author to review it.
    """
    import logging
    from datetime import datetime, timezone, timedelta
    from langchain_core.messages import HumanMessage
    from app.clients.confluence_client import ConfluenceClient
    from app.clients import settings
    from langchain_openai import ChatOpenAI

    logger = logging.getLogger(__name__)
    logger.info("Starting Confluence stale architecture review reminder task...")

    if not settings.get("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not found. Skipping Confluence stale architecture review reminder.")
        return "Confluence stale architecture review reminder task skipped (no OpenAI API key)"

    tracked_spaces = settings.get("CONFLUENCE_TRACKED_SPACES", "").split(",")
    if not tracked_spaces or not tracked_spaces[0].strip():
        logger.info("No CONFLUENCE_TRACKED_SPACES configured. Skipping task.")
        return "Confluence stale architecture review reminder task skipped (no spaces configured)"

    confluence_client = ConfluenceClient()
    marker = "<!-- AUTO_GENERATED_CONFLUENCE_STALE_ARCH_REMINDER -->"
    stale_threshold = datetime.now(timezone.utc) - timedelta(days=180)
    llm = ChatOpenAI(temperature=0.7, model="gpt-4o")

    for space in tracked_spaces:
        space = space.strip()
        if not space:
            continue
        try:
            pages_response = confluence_client.client.get_all_pages_from_space(space, expand="version,history.lastUpdated", start=0, limit=100)
            pages = []
            if isinstance(pages_response, list):
                pages = pages_response
            elif isinstance(pages_response, dict) and "results" in pages_response:
                pages = pages_response["results"]

            for page in pages:
                page_id = page.get("id")
                title = page.get("title", "Untitled")

                # Check labels
                labels_response = confluence_client.client.get_page_labels(page_id)
                labels = []
                if isinstance(labels_response, dict) and "results" in labels_response:
                    labels = labels_response["results"]
                elif isinstance(labels_response, list):
                    labels = labels_response

                label_names = [l.get("name", "").lower() for l in labels]
                if "architecture" not in label_names and "arch" not in label_names:
                    continue

                version_info = page.get("version", {})
                when_str = version_info.get("when")
                if when_str:
                    try:
                        when_dt = datetime.strptime(when_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                        if when_dt < stale_threshold:
                            # Check existing comments
                            comments_response = confluence_client.client.get_page_comments(page_id, expand="body.storage")
                            comments = []
                            if isinstance(comments_response, dict) and "results" in comments_response:
                                comments = comments_response["results"]
                            elif isinstance(comments_response, list):
                                comments = comments_response

                            already_reminded = False
                            for comment in comments:
                                body = comment.get("body", {}).get("storage", {}).get("value", "")
                                if marker in body:
                                    already_reminded = True
                                    break

                            if not already_reminded:
                                author_id = page.get("history", {}).get("lastUpdated", {}).get("by", {}).get("accountId")
                                author_mention = f"[~accountid:{author_id}] " if author_id else ""

                                prompt = (
                                    f"Сгенерируй короткое и вежливое напоминание (в 1-2 предложениях) автору архитектурного документа в Confluence '{title}', "
                                    "о том, что документ не пересматривался более полугода. Попроси проверить его актуальность и обновить или заархивировать, если он устарел. "
                                    "Не используй Markdown форматирование. Пиши просто текст."
                                )
                                response = await llm.ainvoke([HumanMessage(content=prompt)])

                                comment_body = f"{marker}\n{author_mention}{response.content}"
                                confluence_client.client.add_comment(page_id, comment_body)
                                logger.info(f"Added stale architecture reminder to Confluence page '{title}' ({page_id}).")

                    except Exception as e:
                        logger.error(f"Error parsing date or adding comment for page {page_id}: {e}")

        except Exception as e:
            logger.error(f"Error processing Confluence space {space} for stale architecture pages: {e}")

    return "Confluence stale architecture review reminder task completed."

async def gitlab_mr_wip_limit_reminder_task():
    """
    Checks the number of open Merge Requests per author in tracked GitLab projects.
    If an author has more than 3 open MRs, generates a polite message (in Russian) using the LLM
    reminding them of the WIP (Work In Progress) limits and encourages them to focus on closing existing MRs.
    The reminder is posted to their most recently created open MR.
    """
    import logging
    from collections import defaultdict
    from langchain_core.messages import HumanMessage
    global GitLabClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    gitlab_client = GitLabClient()
    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    if not tracked_projects:
        logger.info("No GitLab projects tracked for WIP limit reminder.")
        return "No projects tracked"

    # Dictionary to hold lists of open MRs by author username
    author_mrs = defaultdict(list)

    for project_id in tracked_projects:
        try:
            mrs = gitlab_client.get_project_merge_requests(project_id, state="opened")
            for mr in mrs:
                author_username = mr.author['username']
                author_mrs[author_username].append((project_id, mr))
        except Exception as e:
            logger.error(f"Error fetching MRs for project {project_id}: {e}")
            continue

    WIP_LIMIT = 3

    # Initialize LLM only if there are authors exceeding the WIP limit
    llm = None
    marker = "<!-- AUTO_GENERATED_WIP_LIMIT_REMINDER -->"

    for author, mr_list in author_mrs.items():
        if len(mr_list) > WIP_LIMIT:
            if llm is None:
                llm = ChatOpenAI(temperature=0.7, model="gpt-4o")
            logger.info(f"Author {author} has {len(mr_list)} open MRs, exceeding WIP limit of {WIP_LIMIT}.")

            # Find the most recently created MR for this author
            # mr.created_at is typically an ISO format string, which sorts correctly
            most_recent_mr_tuple = sorted(mr_list, key=lambda x: x[1].created_at, reverse=True)[0]
            target_project_id, target_mr = most_recent_mr_tuple

            try:
                # Check if we already notified on this specific MR
                notes = target_mr.notes.list(all=True)
                already_notified = any(marker in note.body for note in notes)

                if already_notified:
                    logger.info(f"Already notified {author} about WIP limit on MR !{target_mr.iid}.")
                    continue

                prompt = (
                    f"Разработчик @{author} превысил лимит WIP (Work In Progress), имея {len(mr_list)} открытых Merge Requests. "
                    "Лимит равен 3. "
                    "Напиши очень вежливое, дружелюбное и короткое сообщение (1-2 абзаца) на русском языке для комментария в его последнем MR. "
                    "Сообщение должно мягко напомнить о важности доведения начатых задач до конца (фокус на завершении текущих MR), "
                    "прежде чем брать в работу новые. Не будь токсичным, будь как заботливый скрам-мастер."
                )

                response = await llm.ainvoke([HumanMessage(content=prompt)])
                comment_body = f"{response.content}\n\n{marker}"

                gitlab_client.create_mr_note(target_project_id, target_mr.iid, comment_body)
                logger.info(f"Posted WIP limit reminder for {author} on project {target_project_id}, MR !{target_mr.iid}.")

            except Exception as e:
                logger.error(f"Error processing WIP limit reminder for {author} on MR !{target_mr.iid}: {e}")

    return "GitLab MR WIP limit reminder task completed"

async def jira_stale_in_progress_reminder_task():
    """
    Checks Jira tasks that have been in 'In Progress' status for more than 5 days
    without any updates. Posts a reminder comment asking for a status update.
    """


    logger = logging.getLogger(__name__)
    logger.info("Starting automated Jira stale 'In Progress' reminder task...")

    if not settings.get("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not found. Skipping Jira stale 'In Progress' reminder.")
        return "Jira stale 'In Progress' reminder task skipped (no OpenAI API key)"

    jira_client = JiraClient()
    tracked_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_JIRA_STALE_IN_PROGRESS_REMINDER -->"
    llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

    for j_proj in tracked_projects:
        jql = f'project = "{j_proj}" AND status = "In Progress" AND updated <= -5d'
        try:
            issues = jira_client.search_issues(jql)
            for issue in issues:
                comments = jira_client.get_comments(issue.key)
                already_reminded = any(
                    reminder_marker in (c.body or "") for c in comments
                )
                if already_reminded:
                    logger.info(f"Already sent stale 'In Progress' reminder for Jira task {issue.key}.")
                    continue

                assignee_name = issue.fields.assignee.displayName if issue.fields.assignee else "Команда"

                try:
                    prompt = (
                        f"Ты ассистент технического лидера, который помогает следить за процессом разработки. "
                        f"Напишите короткое, вежливое сообщение автору/исполнителю ({assignee_name}) задачи Jira ({issue.key}), "
                        f"которая находится в статусе 'In Progress' более 5 дней без обновлений. "
                        f"Спросите, нужна ли помощь, есть ли какие-то блокеры, и попросите обновить статус задачи, если она уже выполнена. "
                        f"В конце добавь скрытый маркер: {reminder_marker}"
                    )

                    response = llm.invoke([HumanMessage(content=prompt)])
                    comment_body = response.content

                    jira_client.add_comment(issue.key, comment_body)
                    logger.info(f"Added stale 'In Progress' reminder to Jira task {issue.key}")
                except Exception as e:
                    logger.error(f"Failed to generate/post stale 'In Progress' reminder for {issue.key}: {e}")

        except Exception as e:
            logger.error(f"Failed to process Jira stale 'In Progress' reminder for project {j_proj}: {e}")

    logger.info("Finished Jira stale 'In Progress' reminder task.")
    return "Jira stale 'In Progress' reminder task completed"

async def confluence_missing_diagram_checker_task():
    """
    Checks tracked Confluence spaces for architecture documents (pages with label 'architecture' or 'arch')
    that lack embedded diagrams (e.g. draw.io, plantuml, gliffy, mermaid macros or explicit image attachments).
    If an architecture document lacks diagrams, it adds an automated comment suggesting the addition of a visual diagram.
    """
    import logging
    from langchain_core.messages import HumanMessage
    from app.clients.confluence_client import ConfluenceClient
    from app.clients import settings
    from langchain_openai import ChatOpenAI

    logger = logging.getLogger(__name__)
    logger.info("Starting Confluence missing diagram checker task...")

    if not settings.get("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not found. Skipping Confluence missing diagram checker.")
        return "Confluence missing diagram checker task skipped (no OpenAI API key)"

    tracked_spaces = settings.get("CONFLUENCE_TRACKED_SPACES", "").split(",")
    if not tracked_spaces or not tracked_spaces[0].strip():
        logger.info("No CONFLUENCE_TRACKED_SPACES configured. Skipping task.")
        return "Confluence missing diagram checker task skipped (no spaces configured)"

    confluence_client = ConfluenceClient()
    marker = "<!-- AUTO_GENERATED_CONFLUENCE_MISSING_DIAGRAM_REMINDER -->"
    llm = ChatOpenAI(temperature=0.7, model="gpt-4o")
    diagram_indicators = ["draw.io", "plantuml", "gliffy", "mermaid", "<ac:image", "<img"]

    for space in tracked_spaces:
        space = space.strip()
        if not space:
            continue
        try:
            pages_response = confluence_client.client.get_all_pages_from_space(space, expand="body.storage,version,history.lastUpdated", start=0, limit=100)
            pages = []
            if isinstance(pages_response, list):
                pages = pages_response
            elif isinstance(pages_response, dict) and "results" in pages_response:
                pages = pages_response["results"]

            for page in pages:
                page_id = page.get("id")
                title = page.get("title", "Untitled")

                # Check labels
                labels_response = confluence_client.client.get_page_labels(page_id)
                labels = []
                if isinstance(labels_response, dict) and "results" in labels_response:
                    labels = labels_response["results"]
                elif isinstance(labels_response, list):
                    labels = labels_response

                label_names = [l.get("name", "").lower() for l in labels]
                if "architecture" not in label_names and "arch" not in label_names:
                    continue

                body_storage = page.get("body", {}).get("storage", {}).get("value", "")
                has_diagram = any(indicator in body_storage for indicator in diagram_indicators)

                if not has_diagram:
                    # Check existing comments
                    comments_response = confluence_client.client.get_page_comments(page_id, expand="body.storage")
                    comments = []
                    if isinstance(comments_response, dict) and "results" in comments_response:
                        comments = comments_response["results"]
                    elif isinstance(comments_response, list):
                        comments = comments_response

                    already_reminded = False
                    for comment in comments:
                        body = comment.get("body", {}).get("storage", {}).get("value", "")
                        if marker in body:
                            already_reminded = True
                            break

                    if not already_reminded:
                        author_id = page.get("history", {}).get("lastUpdated", {}).get("by", {}).get("accountId")
                        author_mention = f"[~accountid:{author_id}] " if author_id else ""

                        prompt = (
                            f"Сгенерируй короткое и вежливое напоминание (в 1-2 предложениях) автору архитектурного документа в Confluence '{title}', "
                            "о том, что в документе отсутствуют диаграммы или схемы. Попроси добавить визуализацию (например, draw.io, plantuml, mermaid и т.д.) "
                            "для лучшего понимания архитектуры. "
                            "Не используй Markdown форматирование. Пиши просто текст."
                        )
                        response = await llm.ainvoke([HumanMessage(content=prompt)])

                        comment_body = f"{marker}\n{author_mention}{response.content}"
                        confluence_client.client.add_comment(page_id, comment_body)
                        logger.info(f"Added missing diagram reminder to Confluence page '{title}' ({page_id}).")

        except Exception as e:
            logger.error(f"Error processing Confluence space {space} for missing diagrams: {e}")

    return "Confluence missing diagram checker task completed."


async def gitlab_mr_missing_tests_checker_task():
    """
    Iterates over open MRs for tracked projects.
    Checks if an MR modifies source files but lacks test files.
    If so, generates a polite notification via LLM in Russian asking to add tests.
    """
    import logging
    # Use global imports so mocker can patch them in app.tasks
    global GitLabClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting GitLab MR missing tests checker task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping missing tests checker.")
        return "GitLab MR missing tests checker task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)

    gitlab_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    gitlab_projects = [p.strip() for p in gitlab_projects if p.strip()]

    client = GitLabClient()
    reminder_marker = "<!-- AUTO_GENERATED_MISSING_TESTS_COMMENT -->"

    # Simple heuristic for common source and test files
    source_extensions = ('.py', '.js', '.ts', '.java', '.go', '.cpp', '.c', '.rb', '.php')
    test_indicators = ('test_', '_test', '.spec.', 'tests/', 'test/')

    for project_id in gitlab_projects:
        try:
            project = client.client.projects.get(project_id)
            mrs = project.mergerequests.list(state='opened', get_all=True)

            for mr in mrs:
                # Fetch MR object directly to get changes
                mr_obj = project.mergerequests.get(mr.iid)
                changes = mr_obj.changes()

                has_source_changes = False
                has_test_changes = False

                for change in changes.get('changes', []):
                    new_path = change.get('new_path', '').lower()

                    if any(new_path.endswith(ext) for ext in source_extensions):
                        if any(ind in new_path for ind in test_indicators):
                            has_test_changes = True
                        else:
                            has_source_changes = True

                if has_source_changes and not has_test_changes:
                    mr_notes = mr_obj.notes.list(get_all=True)
                    already_notified = any(reminder_marker in note.body for note in mr_notes)

                    if not already_notified:
                        prompt = (
                            f"Сгенерируй короткое и вежливое напоминание (в 1-2 предложениях) автору Merge Request '{mr.title}', "
                            "о том, что в MR изменен исходный код, но не добавлено и не изменено ни одного теста. "
                            "Попроси добавить тесты, если это применимо для данных изменений. "
                            f"Обязательно включи этот скрытый HTML маркер где-нибудь в ответе: {reminder_marker}\n"
                            "Не используй Markdown форматирование. Пиши просто текст."
                        )
                        response = await llm.ainvoke(prompt)
                        comment_body = response.content

                        client.create_mr_note(project_id, mr.iid, comment_body)
                        logger.info(f"Added missing tests reminder to MR {mr.iid} in project {project_id}")
        except Exception as e:
            logger.error(f"Error processing project {project_id} in missing tests checker task: {e}")

    return "GitLab MR missing tests checker task completed."


async def gitlab_mr_missing_changelog_checker_task():
    """
    Iterates over open MRs for tracked projects.
    Checks if an MR modifies source files but lacks changelog updates.
    If so, generates a polite notification via LLM in Russian asking to update the changelog.
    """
    import logging
    # Use global imports so mocker can patch them in app.tasks
    global GitLabClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting GitLab MR missing changelog checker task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping missing changelog checker.")
        return "GitLab MR missing changelog checker task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)

    gitlab_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    gitlab_projects = [p.strip() for p in gitlab_projects if p.strip()]

    client = GitLabClient()
    reminder_marker = "<!-- AUTO_GENERATED_MISSING_CHANGELOG_COMMENT -->"

    source_extensions = ('.py', '.js', '.ts', '.java', '.go', '.cpp', '.c', '.rb', '.php', '.html', '.css', '.vue', '.jsx', '.tsx')

    for project_id in gitlab_projects:
        try:
            project = client.client.projects.get(project_id)
            mrs = project.mergerequests.list(state='opened', get_all=True)

            for mr in mrs:
                mr_obj = project.mergerequests.get(mr.iid)
                changes = mr_obj.changes()

                has_source_changes = False
                has_changelog_changes = False

                for change in changes.get('changes', []):
                    new_path = change.get('new_path', '').lower()

                    if any(new_path.endswith(ext) for ext in source_extensions):
                        has_source_changes = True

                    if 'changelog' in new_path:
                        has_changelog_changes = True

                if has_source_changes and not has_changelog_changes:
                    mr_notes = mr_obj.notes.list(get_all=True)
                    already_notified = any(reminder_marker in note.body for note in mr_notes)

                    if not already_notified:
                        prompt = (
                            f"Сгенерируй короткое и вежливое напоминание (в 1-2 предложениях) автору Merge Request '{mr.title}', "
                            "о том, что в MR изменен исходный код, но не обновлен файл changelog. "
                            "Попроси добавить описание изменений в changelog, если это требуется. "
                            f"Обязательно включи этот скрытый HTML маркер где-нибудь в ответе: {reminder_marker}\n"
                            "Не используй Markdown форматирование. Пиши просто текст."
                        )
                        response = await llm.ainvoke(prompt)
                        comment_body = response.content

                        client.create_mr_note(project_id, mr.iid, comment_body)
                        logger.info(f"Added missing changelog reminder to MR {mr.iid} in project {project_id}")
        except Exception as e:
            logger.error(f"Error processing project {project_id} in missing changelog checker task: {e}")

    return "GitLab MR missing changelog checker task completed."

async def jira_stale_bug_escalation_task():
    """
    Checks for "Bug" type issues open for more than 30 days.
    If found, leaves an automated comment escalating the bug and tags the reporter.
    """
    logger.info("Running Jira stale bug escalation task.")

    openai_api_key = settings.get("OPENAI_API_KEY")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not set. Skipping stale bug escalation task.")
        return "Jira stale bug escalation task skipped (no OpenAI API key)"

    jira_client = JiraClient()
    jira_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")

    llm = ChatOpenAI(temperature=0.7, model="gpt-4o-mini", api_key=openai_api_key)

    import dateutil.parser
    from datetime import datetime, timezone

    for j_proj in jira_projects:
        j_proj = j_proj.strip()
        if not j_proj:
            continue

        jql = f'project = "{j_proj}" AND issuetype = "Bug" AND statusCategory != "Done"'
        issues = jira_client.search_issues(jql)

        for issue in issues:
            updated_str = getattr(issue.fields, "updated", None)
            if not updated_str:
                continue

            try:
                updated_at = dateutil.parser.isoparse(updated_str)
            except Exception:
                continue

            days_inactive = (datetime.now(timezone.utc) - updated_at).days
            if days_inactive > 30:
                # Check for existing comment
                comments = jira_client.get_comments(issue.key)
                already_commented = False
                for c in comments:
                    if hasattr(c, 'body') and "<!-- AUTO_GENERATED_JIRA_STALE_BUG_ESCALATION -->" in c.body:
                        already_commented = True
                        break

                if already_commented:
                    continue

                reporter = getattr(issue.fields, "reporter", None)
                assignee = getattr(issue.fields, "assignee", None)

                reporter_tag = f"[~accountid:{reporter.accountId}]" if reporter and hasattr(reporter, "accountId") else "Создатель"
                assignee_tag = f"[~accountid:{assignee.accountId}]" if assignee and hasattr(assignee, "accountId") else "Исполнитель"

                summary = getattr(issue.fields, "summary", "Без названия")

                prompt = ChatPromptTemplate.from_messages([
                    SystemMessage(content="You are an AI assistant that helps tech leaders manage Jira issues. Generate a polite but firm comment in Russian to escalate a bug that has been open and inactive for more than 30 days. Do not include markdown formatting or quotation marks in your response. The comment should ask about the status and if help is needed to resolve it."),
                    HumanMessage(content=f"Generate an escalation comment for the bug '{summary}'. The reporter is {reporter_tag} and the assignee is {assignee_tag}. Address the reporter directly to ask for an update.")
                ])
                response = await llm.ainvoke(prompt)

                comment_body = f"<!-- AUTO_GENERATED_JIRA_STALE_BUG_ESCALATION -->\n{response.content}"

                jira_client.add_comment(issue.key, comment_body)
                logger.info(f"Added stale bug escalation comment to {issue.key}")

    return "Jira stale bug escalation task completed."

async def gitlab_mr_description_template_validator_task():
    """
    Checks if open MRs contain required sections (e.g., `# How to test`) in their description.
    If missing, posts a reminder to follow the template.
    """
    import logging
    from langchain_core.messages import HumanMessage, SystemMessage
    global GitLabClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting automated GitLab MR description template validator task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping GitLab MR description template validator.")
        return "GitLab MR description template validator task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    gitlab_client = GitLabClient()
    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    reminder_marker = "<!-- AUTO_GENERATED_MR_DESCRIPTION_TEMPLATE_VALIDATOR -->"
    required_section = "# How to test"

    for gl_proj in tracked_projects:
        try:
            mrs = gitlab_client.get_project_mrs(gl_proj, state="opened")
            for mr_data in mrs:
                description = mr_data.get("description") or ""

                if required_section.lower() in description.lower():
                    continue

                mr_iid = mr_data.get("iid")
                notes = gitlab_client.get_mr_notes(gl_proj, mr_iid)
                already_reminded = any(reminder_marker in getattr(n, "body", "") for n in notes)

                if already_reminded:
                    continue

                author = mr_data.get("author", {})
                author_username = author.get("username", "")
                mention = f"@{author_username}" if author_username else "Автор"

                prompt = (
                    f"Ты - Quality Assurance Lead. Напиши вежливый комментарий (на русском языке) для "
                    f"Merge Request !{mr_iid}. Упомяни {mention} и обрати внимание, что в описании MR отсутствует "
                    f"обязательный раздел `{required_section}`. Попроси добавить этот раздел и описать, как именно нужно "
                    f"тестировать изменения. Без приветствий, просто текст."
                )

                resp = await llm.ainvoke([
                    SystemMessage(content="Ты — технический ассистент, помогающий командам соблюдать процессы разработки и тестирования."),
                    HumanMessage(content=prompt)
                ])
                comment_text = f"{reminder_marker}\n{resp.content.strip()}"

                gitlab_client.create_mr_note(gl_proj, mr_iid, comment_text)
                logger.info(f"Posted missing template section reminder for GitLab MR !{mr_iid} in project {gl_proj}.")

        except Exception as e:
            logger.error(f"Failed to process GitLab MR template validator for project {gl_proj}: {e}")

    return "GitLab MR description template validator task completed."

async def gitlab_mr_conflict_checker_task():
    """
    Checks if open MRs in tracked GitLab projects have merge conflicts.
    If so, posts an automated reminder to the author to resolve them.
    """
    import logging
    from langchain_core.messages import HumanMessage, SystemMessage
    global GitLabClient, ChatOpenAI, settings

    logger = logging.getLogger(__name__)
    logger.info("Starting automated GitLab MR conflict checker task...")

    openai_api_key = settings.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("OPENAI_API_KEY not found. Skipping GitLab MR conflict checker.")
        return "GitLab MR conflict checker task skipped (no OpenAI API key)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)
    gitlab_client = GitLabClient()
    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

    if not tracked_projects:
        logger.info("No GitLab projects tracked for conflict checker.")
        return "No projects tracked"

    reminder_marker = "<!-- AUTO_GENERATED_GITLAB_MR_CONFLICT_CHECKER -->"

    for project_id in tracked_projects:
        try:
            mrs = gitlab_client.client.projects.get(project_id).mergerequests.list(state='opened', get_all=True)
            for mr in mrs:
                try:
                    # has_conflicts is a boolean property on MRs in python-gitlab
                    if getattr(mr, "has_conflicts", False):
                        # Check if we already left a reminder
                        notes = mr.notes.list(all=True)
                        already_commented = any(
                            hasattr(n, 'body') and reminder_marker in n.body for n in notes
                        )

                        if not already_commented:
                            # Generate a friendly reminder message via LLM
                            system_prompt = (
                                "You are an AI assistant for a software development team. "
                                "Your task is to write a polite message to the author of a GitLab Merge Request "
                                "informing them that their Merge Request has merge conflicts that need to be resolved. "
                                "Respond in Russian."
                            )
                            user_prompt = f"Write a short, polite message informing the author of MR !{mr.iid} that they need to resolve merge conflicts."
                            messages = [
                                SystemMessage(content=system_prompt),
                                HumanMessage(content=user_prompt)
                            ]

                            response = await llm.ainvoke(messages)
                            comment_body = f"{reminder_marker}\n{response.content}"

                            gitlab_client.create_mr_note(project_id, mr.iid, comment_body)
                            logger.info(f"Posted MR conflict reminder to MR !{mr.iid} in project {project_id}.")
                except Exception as e:
                    logger.error(f"Error processing MR !{getattr(mr, 'iid', 'unknown')} in project {project_id} for conflict checker: {e}")
        except Exception as e:
            logger.error(f"Error fetching MRs for project {project_id} in conflict checker: {e}")

    logger.info("Finished GitLab MR conflict checker task.")
    return "GitLab MR conflict checker task completed"
