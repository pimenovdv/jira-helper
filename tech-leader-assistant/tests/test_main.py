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
