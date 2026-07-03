from fastapi import FastAPI, Depends
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
