from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from contextlib import asynccontextmanager
from .clients.gitlab_client import GitLabClient
from .clients.jira_client import JiraClient
from .clients.confluence_client import ConfluenceClient
from .clients.neo4j_client import Neo4jClient
from .clients.opensearch_client import OpenSearchClient
from .scheduler import start_scheduler, shutdown_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start APScheduler
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

@app.get("/")
async def root():
    index_path = static_dir / "index.html"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Static files not found</h1>")
