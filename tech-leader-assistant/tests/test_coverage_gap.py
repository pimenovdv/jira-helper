from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.clients import settings
from unittest.mock import MagicMock
import json


from app.main import get_db

async def override_get_db():
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)
    yield mock_session

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def patch_astext(monkeypatch):
    from sqlalchemy.sql.elements import BinaryExpression
    monkeypatch.setattr(BinaryExpression, "astext", property(lambda self: self), raising=False)


@pytest.fixture(autouse=True)
def restore_settings():
    orig_jira = settings.get("JIRA_TRACKED_PROJECTS")
    orig_gitlab = settings.get("GITLAB_TRACKED_PROJECTS")
    yield
    settings.set("JIRA_TRACKED_PROJECTS", orig_jira)
    settings.set("GITLAB_TRACKED_PROJECTS", orig_gitlab)

def test_delete_stale_branch_main(mocker):
    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_gl.delete_branch.return_value = True

    response = client.post("/api/stale-branches/delete", json={"project_id": "p1", "branch_name": "b1"})
    assert response.status_code == 200

    mock_gl.delete_branch.return_value = False
    response = client.post("/api/stale-branches/delete", json={"project_id": "p1", "branch_name": "b1"})
    assert response.status_code == 500

def test_chat_endpoint(mocker):
    mock_graph = mocker.patch('app.main.app_graph')
    mock_graph.invoke.return_value = {"messages": [MagicMock(content="Mock response")]}

    response = client.post("/api/chat", json={"query": "Hello"})
    assert response.status_code == 200
    pass

    mock_graph.invoke.side_effect = Exception("Fail")
    response = client.post("/api/chat", json={"query": "Hello"})
    assert response.status_code == 500

def test_get_user_timeline(mocker):
    # Coverage for get_user_timeline
    response = client.get("/api/timeline/user/user1")
    assert response.status_code == 200

def test_get_project_timeline(mocker):
    # Coverage for get_project_timeline
    response = client.get("/api/timeline/project/proj1")
    assert response.status_code == 200

def test_override_confluence_link_success(mocker):
    # Covers override_confluence_link success path


    # Actually need to pass depending on get_db, fast api test client lets us hit the route
    response = client.post("/api/confluence/override", json={
        "page_id": "1",
        "project_id": "p1",
        "action": "link"
    })
    assert response.status_code == 200

def test_override_confluence_link_fail(mocker):
    response = client.post("/api/confluence/override", json={
        "page_id": "1",
        "project_id": "p1",
        "action": "unknown"
    })
    assert response.status_code == 400


def test_get_stale_branches_list(mocker):
    # Covers lines 291-358
    settings.set("GITLAB_TRACKED_PROJECTS", "proj1")

    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_jira = mocker.patch('app.main.JiraClient').return_value

    class MockCommit(dict):
        def get(self, key, default=None):
            if key == 'committed_date':
                return "2020-01-01T00:00:00.000Z"
            return super().get(key, default)

    class MockBranch:
        def __init__(self, name):
            self.name = name
            self.commit = MockCommit()

    mock_gl.get_project_branches.return_value = [MockBranch("PROJ-123")]

    class MockFields:
        status = MagicMock(name="Done")

    class MockIssue:
        key = "PROJ-123"
        fields = MockFields()

    mock_jira.search_issues.return_value = [MockIssue()]
    MockFields.status.name = "done"

    # Need to append ?days=30 to hit the query parameter correctly maybe?
    response = client.get("/api/stale-branches?days=30")
    assert response.status_code == 200
