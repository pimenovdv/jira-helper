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
from app.clients import settings
from app.clients.confluence_client import ConfluenceClient
from app.clients.neo4j_client import Neo4jClient

global GitLabClient, settings
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
    from langchain_core.messages import HumanMessage, AIMessage

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


async def gitlab_empty_mr_description_notifier_task():
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
