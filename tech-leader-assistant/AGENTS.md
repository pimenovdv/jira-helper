# AGENTS.md - Developer Guidelines

## Project Architecture

This project is a Tech Leader Assistant using FastAPI.

### Directory Structure

```
tech-leader-assistant/
├── app/
│   ├── main.py        # FastAPI application and route definitions
│   ├── clients/       # Wrappers for external systems
│       ├── __init__.py
│       ├── base.py
│       ├── gitlab_client.py
│       ├── jira_client.py
│       ├── confluence_client.py
│       ├── neo4j_client.py
│       ├── opensearch_client.py
│   ├── static/        # Frontend assets (HTML, JS, CSS)
│       ├── index.html
│       ├── main.js
├── settings.toml      # Dynaconf configurations
├── Dockerfile         # Docker instructions for backend+frontend
├── docker-compose.yml # Orchestration for App, Neo4j, OpenSearch
├── pyproject.toml     # Python dependencies
├── todo.md            # Project planning and features
```

## Coding Conventions

1. **FastAPI**: Use asynchronous handlers where possible. Keep `main.py` clean by eventually delegating logic to routers.
2. **Clients**: Initialize clients globally or via dependencies. Do not hardcode credentials; use `dynaconf`.
3. **Frontend**: Keep the initial frontend strictly simple (vanilla JS, HTML) served directly by FastAPI via `StaticFiles`.
4. **Environment**: We use `uv` for dependency management.

## Testing & Validation
- Start the server using `uvicorn app.main:app --reload`.
- Ensure `/api/health` endpoint correctly reports the status of all dummy external clients.
