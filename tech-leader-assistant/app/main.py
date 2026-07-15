from app.deep_research import deep_research_graph
from fastapi import FastAPI, Depends
import re
from datetime import datetime, timezone, timedelta
from .clients import settings

from pydantic import BaseModel
from fastapi import HTTPException
from datetime import datetime

from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from contextlib import asynccontextmanager
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .clients.gitlab_client import GitLabClient
from .clients.jira_client import JiraClient
from .clients.confluence_client import ConfluenceClient
from .clients.neo4j_client import Neo4jClient
from .clients.opensearch_client import OpenSearchClient
from .scheduler import start_scheduler, shutdown_scheduler
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import OpenSearchVectorSearch
from .database import get_db, engine, Base
from .models import Event
from .rag import app_graph

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start APScheduler
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    start_scheduler()
    yield
    # Shutdown: Stop APScheduler
    shutdown_scheduler()

app = FastAPI(title="Tech Leader Assistant API", lifespan=lifespan)

# Setup static files directory
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/api/health")
def health_check():
    gitlab_client = GitLabClient()
    jira_client = JiraClient()
    confluence_client = ConfluenceClient()
    neo4j_client = Neo4jClient()
    opensearch_client = OpenSearchClient()

    return {
        "status": "active",
        "clients": [
            gitlab_client.ping(),
            jira_client.ping(),
            confluence_client.ping(),
            neo4j_client.ping(),
            opensearch_client.ping()
        ]
    }

@app.get("/api/timeline/user/{user_id}")
async def get_user_timeline(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Event).where(Event.user_id == user_id).order_by(Event.timestamp.desc()).limit(100)
    )
    events = result.scalars().all()
    return {"user_id": user_id, "events": [{"id": e.id, "type": e.event_type, "timestamp": e.timestamp, "data": e.data} for e in events]}

@app.get("/api/timeline/project/{project_id}")
async def get_project_timeline(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Event).where(Event.project_id == project_id).order_by(Event.timestamp.desc()).limit(100)
    )
    events = result.scalars().all()
    return {"project_id": project_id, "events": [{"id": e.id, "type": e.event_type, "timestamp": e.timestamp, "data": e.data} for e in events]}


@app.get("/api/dashboard/tasks")
async def get_dashboard_tasks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Event).where(Event.event_type == "jira_task_crossmatch").order_by(Event.timestamp.desc())
    )
    events = result.scalars().all()
    tasks = []
    for e in events:
        data = e.data or {}
        tasks.append({
            "task_id": data.get("task_id", ""),
            "summary": data.get("summary", ""),
            "fix_versions": data.get("fix_versions", []),
            "matched_gitlab_projects": data.get("matched_gitlab_projects", []),
            "timestamp": e.timestamp
        })
    return {"tasks": tasks}

@app.get("/api/dashboard/releases")
async def get_dashboard_releases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Event).where(Event.event_type == "jira_release_crossmatch").order_by(Event.timestamp.desc())
    )
    events = result.scalars().all()
    releases = []
    for e in events:
        data = e.data or {}
        releases.append({
            "release_name": data.get("release_name", ""),
            "matched_gitlab_projects": data.get("matched_gitlab_projects", []),
            "ready_for_release": data.get("ready_for_release", False),
            "tasks": data.get("tasks", []),
            "timestamp": e.timestamp
        })
    return {"releases": releases}

class ConfluenceOverrideRequest(BaseModel):
    page_id: str
    project_id: str
    action: str  # 'link' or 'unlink'

@app.post("/api/confluence/override")
async def override_confluence_link(req: ConfluenceOverrideRequest, db: AsyncSession = Depends(get_db)):
    if req.action not in ["link", "unlink"]:
        raise HTTPException(status_code=400, detail="Action must be 'link' or 'unlink'")

    result = await db.execute(
        select(Event).where(
            (Event.event_type == "confluence_project_link") &
            (Event.data["page_id"].astext == req.page_id)
        )
    )
    existing_event = result.scalar_one_or_none()

    if not existing_event:
        # Create a skeleton event if none exists
        event_data = {
            "page_id": req.page_id,
            "page_title": "",
            "auto_linked_projects": [],
            "manual_linked_projects": [req.project_id] if req.action == "link" else [],
            "manual_unlinked_projects": [req.project_id] if req.action == "unlink" else []
        }
        event = Event(
            event_type="confluence_project_link",
            timestamp=datetime.utcnow(),
            data=event_data
        )
        db.add(event)
    else:
        current_data = existing_event.data.copy()

        # Initialize lists if missing
        if "manual_linked_projects" not in current_data:
            current_data["manual_linked_projects"] = []
        if "manual_unlinked_projects" not in current_data:
            current_data["manual_unlinked_projects"] = []

        if req.action == "link":
            if req.project_id not in current_data["manual_linked_projects"]:
                current_data["manual_linked_projects"].append(req.project_id)
            if req.project_id in current_data["manual_unlinked_projects"]:
                current_data["manual_unlinked_projects"].remove(req.project_id)
        elif req.action == "unlink":
            if req.project_id not in current_data["manual_unlinked_projects"]:
                current_data["manual_unlinked_projects"].append(req.project_id)
            if req.project_id in current_data["manual_linked_projects"]:
                current_data["manual_linked_projects"].remove(req.project_id)

        existing_event.data = current_data
        existing_event.timestamp = datetime.utcnow()

    await db.commit()
    return {"status": "success"}

@app.get("/")

async def root():
    index_path = static_dir / "index.html"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Static files not found</h1>")

@app.get("/api/stale-branches")
def get_stale_branches():
    from app.clients import settings
    import re
    import dateutil.parser
    from datetime import datetime, timezone

    gitlab_client = GitLabClient()
    jira_client = JiraClient()

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    jira_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")

    j_projects = [p.strip() for p in jira_projects if p.strip()]
    if not j_projects:
        return {"stale_branches": []}

    jql = "project in (" + ",".join(j_projects) + ") AND status in (Done, Closed)"
    closed_issues = jira_client.search_issues(jql)
    closed_issue_keys = {issue.key for issue in closed_issues}

    stale_branches = []
    now = datetime.now(timezone.utc)

    for pid in tracked_projects:
        pid = pid.strip()
        if not pid: continue

        branches = gitlab_client.get_project_branches(pid)
        for b in branches:
            # Check age
            try:
                commit_date_str = b.attributes.get('commit', {}).get('committed_date')
                if commit_date_str:
                    dt = dateutil.parser.isoparse(commit_date_str)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    age_days = (now - dt).days

                    if age_days > 30:
                        # Check if branch name matches closed issue
                        for issue_key in closed_issue_keys:
                            parts = re.split(r'[^a-zA-Z0-9\-]', b.name)
                            matched = False
                            if issue_key in parts or any(issue_key == p for p in parts) or issue_key in b.name.split('/'):
                                matched = True
                            elif re.search(rf"\b{re.escape(issue_key)}(?!\-?[a-zA-Z0-9])\b", b.name):
                                matched = True

                            if matched:
                                stale_branches.append({
                                    "project_id": pid,
                                    "branch_name": b.name,
                                    "issue_key": issue_key,
                                    "age_days": age_days,
                                    "commit_date": commit_date_str
                                })
                                break # match found, no need to check other issues
            except Exception as e:
                continue

    return {"stale_branches": stale_branches}

class DeleteBranchRequest(BaseModel):
    project_id: str
    branch_name: str

@app.post("/api/stale-branches/delete")
def delete_stale_branch(req: DeleteBranchRequest):
    gitlab_client = GitLabClient()
    success = gitlab_client.delete_branch(req.project_id, req.branch_name)
    if success:
        return {"status": "success"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete branch")


from langchain_core.messages import HumanMessage

class ChatRequest(BaseModel):
    query: str

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    if not req.query:
        raise HTTPException(status_code=400, detail="Query is required")

    try:
        result = app_graph.invoke({"messages": [HumanMessage(content=req.query)]})
        # Extract the final answer from the last message
        final_answer = "No answer found"
        if "messages" in result and len(result["messages"]) > 0:
            final_answer = result["messages"][-1].content

        return {
            "question": req.query,
            "answer": final_answer,
            "documents": [] # Document retrieval is now handled by tools
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DeleteBranchRequest(BaseModel):
    project_id: str
    branch_name: str

@app.get("/api/technical-debt/gap-analysis")
def get_gap_analysis(days: int = 14):
    jira_client = JiraClient()
    confluence_client = ConfluenceClient()
    gitlab_client = GitLabClient()

    jql = f"status IN ('Done', 'Closed') AND updated >= -{days}d"
    issues = jira_client.search_issues(jql)

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
    tracked_projects = [pid.strip() for pid in tracked_projects if pid.strip()]

    # Pre-fetch all merged MRs to avoid N+1 queries
    project_mrs_map = {}
    for pid in tracked_projects:
        project_mrs_map[pid] = gitlab_client.get_project_merge_requests(pid, state="merged")

    technical_debt = []

    for issue in issues:
        task_id = issue.key

        # Check Confluence docs
        cql = f'text ~ "{task_id}"'
        docs = confluence_client.search_cql(cql)
        has_docs = len(docs.get("results", [])) > 0

        # Check MR tests
        has_tests = False
        related_mrs = []

        task_id_pattern = re.compile(r"\b" + re.escape(task_id) + r"\b")

        for pid, mrs in project_mrs_map.items():
            for mr in mrs:
                if task_id_pattern.search(mr.title) or task_id_pattern.search(mr.source_branch):
                    related_mrs.append(mr)
                    changes = gitlab_client.get_merge_request_changes(pid, mr.iid)
                    for change in changes.get("changes", []):
                        if "test" in change.get("new_path", "").lower() or "test" in change.get("old_path", "").lower():
                            has_tests = True
                            break
                if has_tests:
                    break
            if has_tests:
                break

        if not has_docs or (related_mrs and not has_tests):
            technical_debt.append({
                "task_id": task_id,
                "task_summary": getattr(issue.fields, "summary", ""),
                "has_docs": has_docs,
                "has_tests": has_tests,
                "related_mrs": [{"iid": mr.iid, "title": mr.title, "web_url": mr.web_url} for mr in related_mrs]
            })

    return {"technical_debt": technical_debt}

@app.post("/api/projects/{project_id}/merge_requests/{mr_iid}/review")
def create_automated_code_review(project_id: str, mr_iid: int):
    try:
        gitlab_client = GitLabClient()
        changes_data = gitlab_client.get_merge_request_changes(project_id, mr_iid)

        if not changes_data or "changes" not in changes_data:
            raise HTTPException(status_code=404, detail="MR or changes not found")

        changes = changes_data["changes"]
        diffs_text = ""
        for change in changes:
            diffs_text += f"File: {change.get('new_path')}\n"
            diffs_text += f"Diff: {change.get('diff', '')}\n\n"

        openai_api_key = settings.get("OPENAI_API_KEY", "")
        if not openai_api_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not found")

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

        # We query OpenSearch for coding guidelines or relevant context
        docs = retriever.invoke("coding guidelines code review best practices")
        context_text = "\n\n".join([doc.page_content for doc in docs])

        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, openai_api_key=openai_api_key)

        prompt = ChatPromptTemplate.from_template(
            "Ты — опытный разработчик и автоматизированный ассистент code review. "
            "Твоя задача проанализировать изменения в Merge Request и оставить конструктивный отзыв "
            "на основе корпоративных стандартов.\n\n"
            "Корпоративные стандарты (контекст из базы знаний):\n{context}\n\n"
            "Изменения в коде (Git diff):\n{diffs}\n\n"
            "Напиши ревью на русском языке. Укажи на потенциальные ошибки, нарушения стандартов или предложи улучшения. "
            "Если всё выглядит хорошо, так и скажи."
        )

        chain = prompt | llm
        response = chain.invoke({"context": context_text, "diffs": diffs_text})
        review_note = response.content

        success = gitlab_client.create_merge_request_note(project_id, mr_iid, review_note)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to post note to GitLab")

        return {"status": "success", "review": review_note}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bottlenecks/code-review")
def get_code_review_bottlenecks(days: int = 2):
    gitlab_client = GitLabClient()
    jira_client = JiraClient()

    tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    task_mr_map = {}

    for pid in tracked_projects:
        pid = pid.strip()
        if not pid: continue

        mrs = gitlab_client.get_project_merge_requests(pid, state="opened")
        for mr in mrs:
            created_at_str = mr.created_at
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    if created_at > cutoff_date:
                        continue # Not old enough to be a bottleneck
                except Exception:
                    pass

            # Extract task ID from branch name or MR title
            task_id = None
            match_branch = re.search(r'([A-Z]+-\d+)', mr.source_branch)
            if match_branch:
                task_id = match_branch.group(1)
            else:
                match_title = re.search(r'([A-Z]+-\d+)', mr.title)
                if match_title:
                    task_id = match_title.group(1)

            if not task_id:
                continue

            if task_id not in task_mr_map:
                task_mr_map[task_id] = []

            task_mr_map[task_id].append({
                "project_id": pid,
                "mr_iid": mr.iid,
                "mr_title": mr.title,
                "mr_web_url": mr.web_url,
                "created_at": created_at_str,
                "author": mr.author.get('username') if getattr(mr, 'author', None) else 'unknown'
            })

    bottlenecks = []

    if not task_mr_map:
        return {"bottlenecks": []}

    task_ids = list(task_mr_map.keys())
    jql = f"key in ({','.join(task_ids)})"

    issues = jira_client.search_issues(jql)

    for issue in issues:
        status = getattr(getattr(issue.fields, "status", None), "name", "").lower()
        if status in ["in progress", "code review", "review"]:
            # Task is in progress/review, and MR is old, so it's a bottleneck
            if issue.key in task_mr_map:
                bottlenecks.append({
                    "task_id": issue.key,
                    "task_summary": getattr(issue.fields, "summary", ""),
                    "task_status": status,
                    "merge_requests": task_mr_map[issue.key]
                })

    return {"bottlenecks": bottlenecks}

@app.get("/api/debt/gap-analysis")
def get_gap_analysis(days: int = 30):
    try:
        jira_client = JiraClient()

        jira_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
        j_projects = [p.strip() for p in jira_projects if p.strip()]

        if not j_projects:
            return {"debt_tasks": []}

        jql = f"project in ({','.join(j_projects)}) AND status in (Done, Closed) AND resolved >= -{days}d"
        closed_issues = jira_client.search_issues(jql)

        gitlab_client = GitLabClient()
        confluence_client = ConfluenceClient()
        tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
        tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

        debt_tasks = []
        for issue in closed_issues:
            task_id = issue.key
            has_tests = False

            # Check GitLab branches and commits
            for pid in tracked_projects:
                branches = gitlab_client.get_project_branches(pid)
                matching_branches = [b for b in branches if task_id in b.name]

                for branch in matching_branches:
                    commits = gitlab_client.get_project_commits(pid, ref_name=branch.name)
                    for commit in commits:
                        msg = getattr(commit, 'message', '').lower()
                        if 'test' in msg or 'cov' in msg or 'mock' in msg:
                            has_tests = True
                            break
                    if has_tests:
                        break
                if has_tests:
                    break

            # Check Confluence documentation
            has_docs = False
            try:
                cql = f'text ~ "{task_id}"'
                docs_result = confluence_client.search_cql(cql, limit=1)
                if docs_result and docs_result.get("results"):
                    has_docs = True
            except Exception:
                pass

            debt_tasks.append({
                "task_id": task_id,
                "task_summary": getattr(issue.fields, "summary", ""),
                "missing_tests": not has_tests,
                "missing_docs": not has_docs
            })

        return {"debt_tasks": [task for task in debt_tasks if task["missing_tests"] or task["missing_docs"]]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrics/developer-velocity")
def get_developer_velocity(days: int = 30):
    try:
        jira_client = JiraClient()
        gitlab_client = GitLabClient()
        confluence_client = ConfluenceClient()

        jira_projects = settings.get("JIRA_TRACKED_PROJECTS", "").split(",")
        j_projects = [p.strip() for p in jira_projects if p.strip()]

        if not j_projects:
            return {"velocity_metrics": []}

        jql = f"project in ({','.join(j_projects)}) AND status in (Done, Closed) AND resolved >= -{days}d"
        closed_issues = jira_client.search_issues(jql)

        tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")
        tracked_projects = [p.strip() for p in tracked_projects if p.strip()]

        metrics = []

        for issue in closed_issues:
            task_id = issue.key
            created_str = getattr(issue.fields, "created", None)
            resolved_str = getattr(issue.fields, "resolutiondate", None)

            completion_time_days = 0
            if created_str and resolved_str:
                try:
                    fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
                    try:
                        created_date = datetime.strptime(created_str, fmt)
                        resolved_date = datetime.strptime(resolved_str, fmt)
                    except ValueError:
                        fmt_no_ms = "%Y-%m-%dT%H:%M:%S%z"
                        created_date = datetime.strptime(created_str, fmt_no_ms)
                        resolved_date = datetime.strptime(resolved_str, fmt_no_ms)

                    completion_time_days = (resolved_date - created_date).days
                except Exception:
                    pass

            mr_count = 0
            commit_count = 0

            for pid in tracked_projects:
                mrs = gitlab_client.get_project_merge_requests(pid, state="all")
                for mr in mrs:
                    if task_id in mr.title or task_id in mr.source_branch:
                        mr_count += 1

                branches = gitlab_client.get_project_branches(pid)
                matching_branches = [b for b in branches if task_id in b.name]
                for branch in matching_branches:
                    commits = gitlab_client.get_project_commits(pid, ref_name=branch.name)
                    commit_count += len(commits)

            is_low_velocity = completion_time_days > 5

            possible_causes = []
            if is_low_velocity:
                cql = f'text ~ "{task_id}"'
                docs = confluence_client.search_cql(cql)
                for doc in docs.get("results", []):
                    possible_causes.append({
                        "title": doc.get("title", ""),
                        "url": f"{confluence_client.url}{doc.get('_links', {}).get('webui', '')}"
                    })

            metrics.append({
                "task_id": task_id,
                "task_summary": getattr(issue.fields, "summary", ""),
                "completion_time_days": completion_time_days,
                "mr_count": mr_count,
                "commit_count": commit_count,
                "is_low_velocity": is_low_velocity,
                "possible_causes": possible_causes
            })

        return {"velocity_metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DeepResearchRequest(BaseModel):
    query: str

@app.post("/api/deep-research")
def perform_deep_research(req: DeepResearchRequest):
    try:
        # We start the graph
        initial_state = {
            "original_query": req.query,
            "plan": [],
            "current_task_id": None,
            "completed_tasks": {},
            "task_results": {},
            "final_report": "",
            "messages": []
        }

        # Invoke is synchronous and blocks until END
        result = deep_research_graph.invoke(initial_state)

        return {
            "status": "success",
            "report": result.get("final_report", ""),
            "plan": [p.model_dump() for p in result.get("plan", [])],
            "task_results": result.get("task_results", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
