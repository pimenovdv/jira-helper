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

class ChatRequest(BaseModel):
    query: str

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    if not req.query:
        raise HTTPException(status_code=400, detail="Query is required")

    try:
        result = app_graph.invoke({"question": req.query})
        return {
            "question": req.query,
            "answer": result.get("answer", "No answer found"),
            "documents": result.get("documents", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DeleteBranchRequest(BaseModel):
    project_id: str
    branch_name: str

@app.get("/api/stale-branches")
def get_stale_branches(days: int = 30):
    try:
        gitlab_client = GitLabClient()
        jira_client = JiraClient()

        tracked_projects = settings.get("GITLAB_TRACKED_PROJECTS", "").split(",")

        stale_branches = []
        task_branch_map = {}

        # Calculate the cutoff date
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        for pid in tracked_projects:
            pid = pid.strip()
            if not pid: continue

            branches = gitlab_client.get_project_branches(pid)
            for branch in branches:
                branch_name = branch.name

                # Extract task ID (e.g., PROJ-123)
                match = re.search(r'([A-Z]+-\d+)', branch_name)
                if not match:
                    continue

                task_id = match.group(1)

                # Check commit date
                commit_date_str = branch.commit.get('committed_date') if getattr(branch, 'commit', None) else None
                if commit_date_str:
                    try:
                        # ISO 8601 string from GitLab, parse it
                        commit_date = datetime.fromisoformat(commit_date_str.replace("Z", "+00:00"))
                        if commit_date.tzinfo is None:
                            commit_date = commit_date.replace(tzinfo=timezone.utc)
                        if commit_date > cutoff_date:
                            continue # Not stale enough
                    except Exception:
                        pass # Couldn't parse date, maybe keep it to be safe or ignore? Let's check Jira anyway.

                if task_id not in task_branch_map:
                    task_branch_map[task_id] = []

                task_branch_map[task_id].append({
                    "project_id": pid,
                    "branch_name": branch_name,
                    "commit_date": commit_date_str
                })

        if not task_branch_map:
            return {"stale_branches": []}

        # Batch query Jira for these tasks
        task_ids = list(task_branch_map.keys())
        jql = f"key in ({','.join(task_ids)})"

        issues = jira_client.search_issues(jql)

        for issue in issues:
            status = getattr(getattr(issue.fields, "status", None), "name", "").lower()
            if status in ["done", "closed"]:
                # Tasks are done, these branches are stale
                if issue.key in task_branch_map:
                    stale_branches.extend(task_branch_map[issue.key])

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"stale_branches": stale_branches}

@app.post("/api/stale-branches/delete")
def delete_stale_branch(req: DeleteBranchRequest):
    gitlab_client = GitLabClient()
    success = gitlab_client.delete_branch(req.project_id, req.branch_name)
    if success:
        return {"status": "success"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete branch")

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
