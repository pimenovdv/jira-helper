import pytest
from fastapi.testclient import TestClient
from app.main import app
import json

@pytest.fixture(autouse=True)
def mock_astext(monkeypatch):
    from sqlalchemy.sql.elements import BinaryExpression
    monkeypatch.setattr(BinaryExpression, "astext", property(lambda self: self), raising=False)

client = TestClient(app)

def test_health_check(mocker):
    mocker.patch('app.main.GitLabClient').return_value.ping.return_value = {"status": "ok"}
    mocker.patch('app.main.JiraClient').return_value.ping.return_value = {"status": "ok"}
    mocker.patch('app.main.ConfluenceClient').return_value.ping.return_value = {"status": "ok"}
    mocker.patch('app.main.Neo4jClient').return_value.ping.return_value = {"status": "ok"}
    mocker.patch('app.main.OpenSearchClient').return_value.ping.return_value = {"status": "ok"}

    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "active"

@pytest.mark.asyncio
async def test_override_confluence_link(mocker):
    mock_db = mocker.AsyncMock()
    mock_result = mocker.MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[app.dependency_overrides.get("get_db", lambda: None)] = lambda: mock_db

    from app.main import get_db
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.post(
        "/api/confluence/override",
        json={"page_id": "123", "project_id": "999", "action": "link"}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success"}

    mock_db.add.assert_called_once()
    added_event = mock_db.add.call_args[0][0]
    assert added_event.event_type == "confluence_project_link"
    assert "999" in added_event.data["manual_linked_projects"]

    mock_db.commit.assert_called_once()
    app.dependency_overrides.clear()

def test_chat_endpoint(mocker):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    mock_invoke = mocker.patch("app.main.app_graph.invoke")
    mock_invoke.return_value = {
        "question": "Hello",
        "answer": "Test answer",
        "documents": ["Doc 1"]
    }

    response = client.post("/api/chat", json={"query": "Hello"})
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "Hello"
    assert data["answer"] == "Test answer"
    assert data["documents"] == ["Doc 1"]

    mock_invoke.assert_called_once_with({"question": "Hello"})

def test_chat_endpoint_empty_query():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    response = client.post("/api/chat", json={"query": ""})
    assert response.status_code == 400
    assert response.json()["detail"] == "Query is required"

@pytest.mark.asyncio
async def test_get_dashboard_tasks(mocker):
    mock_db = mocker.AsyncMock()
    mock_result = mocker.MagicMock()

    class MockEvent:
        def __init__(self, task_id, summary, fix_versions, matched_gitlab_projects):
            self.event_type = "jira_task_crossmatch"
            from datetime import datetime
            self.timestamp = datetime.now()
            self.data = {
                "task_id": task_id,
                "summary": summary,
                "fix_versions": fix_versions,
                "matched_gitlab_projects": matched_gitlab_projects
            }

    mock_events = [
        MockEvent("TASK-1", "Fix a bug", ["v1.0"], ["project1"]),
        MockEvent("TASK-2", "Add feature", [], [])
    ]

    mock_result.scalars.return_value.all.return_value = mock_events
    mock_db.execute.return_value = mock_result

    from app.main import get_db
    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.get("/api/dashboard/tasks")

    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert len(data["tasks"]) == 2
    assert data["tasks"][0]["task_id"] == "TASK-1"
    assert data["tasks"][0]["summary"] == "Fix a bug"
    assert data["tasks"][0]["fix_versions"] == ["v1.0"]
    assert data["tasks"][0]["matched_gitlab_projects"] == ["project1"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_dashboard_releases(mocker):
    mock_db = mocker.AsyncMock()
    mock_result = mocker.MagicMock()

    class MockEvent:
        def __init__(self, release_name, matched_gitlab_projects, ready_for_release, tasks):
            self.event_type = "jira_release_crossmatch"
            from datetime import datetime
            self.timestamp = datetime.now()
            self.data = {
                "release_name": release_name,
                "matched_gitlab_projects": matched_gitlab_projects,
                "ready_for_release": ready_for_release,
                "tasks": tasks
            }

    mock_events = [
        MockEvent("v1.0", ["project1"], True, [{"task_id": "TASK-1", "summary": "Fix a bug", "statuses": []}]),
        MockEvent("v2.0", [], False, [])
    ]
    mock_result.scalars().all.return_value = mock_events
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    from app.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    response = client.get("/api/dashboard/releases")

    assert response.status_code == 200
    data = response.json()
    assert "releases" in data
    assert len(data["releases"]) == 2
    assert data["releases"][0]["release_name"] == "v1.0"
    assert data["releases"][0]["matched_gitlab_projects"] == ["project1"]
    assert data["releases"][0]["ready_for_release"] is True
    assert len(data["releases"][0]["tasks"]) == 1
    assert data["releases"][0]["tasks"][0]["task_id"] == "TASK-1"

    app.dependency_overrides.clear()
