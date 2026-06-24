from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from .clients import (
    GitLabDummyClient,
    JiraDummyClient,
    ConfluenceDummyClient,
    Neo4jDummyClient,
    OpenSearchDummyClient
)

app = FastAPI(title="Tech Leader Assistant API")

# Setup static files directory
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/api/health")
async def health_check():
    gitlab_client = GitLabDummyClient()
    jira_client = JiraDummyClient()
    confluence_client = ConfluenceDummyClient()
    neo4j_client = Neo4jDummyClient()
    opensearch_client = OpenSearchDummyClient()

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
