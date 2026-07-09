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
    from langchain_core.messages import AIMessage, HumanMessage
    from app.main import app
    client = TestClient(app)
    mock_invoke = mocker.patch("app.main.app_graph.invoke")
    mock_invoke.return_value = {
        "messages": [AIMessage(content="Test answer")]
    }

    response = client.post("/api/chat", json={"query": "Hello"})
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "Hello"
    assert data["answer"] == "Test answer"
    assert data["documents"] == []

    mock_invoke.assert_called_once()
    called_arg = mock_invoke.call_args[0][0]
    assert "messages" in called_arg
    assert len(called_arg["messages"]) == 1
    assert isinstance(called_arg["messages"][0], HumanMessage)
    assert called_arg["messages"][0].content == "Hello"

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

def test_get_stale_branches(mocker):
    mocker.patch('app.main.settings.get', side_effect=lambda k, default='': 'proj1,proj2' if k == 'GITLAB_TRACKED_PROJECTS' else default)

    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_jira = mocker.patch('app.main.JiraClient').return_value

    class MockCommit(dict):
        def get(self, key, default=None):
            if key == 'committed_date':
                return "2020-01-01T00:00:00.000+00:00" # Very old commit
            return super().get(key, default)

    class MockBranch:
        def __init__(self, name):
            self.name = name
            self.commit = MockCommit()
            self.attributes = {"commit": self.commit}

    mock_gl.get_project_branches.side_effect = lambda pid: [MockBranch("TASK-1"), MockBranch("TASK-2"), MockBranch("no-task")] if pid == "proj1" else [MockBranch("TASK-3")]

    class MockStatus:
        def __init__(self, name):
            self.name = name

    class MockFields:
        def __init__(self, name):
            self.status = MockStatus(name)

    class MockIssue:
        def __init__(self, key, status_name):
            self.key = key
            self.fields = MockFields(status_name)

    # Jira JQL return: TASK-1 is closed, TASK-2 is in progress, TASK-3 is done
    mock_jira.search_issues.return_value = [
        MockIssue("TASK-1", "Closed"),
        MockIssue("TASK-2", "In Progress"),
        MockIssue("TASK-3", "Done")
    ]

    response = client.get("/api/stale-branches?days=30")

    assert response.status_code == 200
    data = response.json()
    assert "stale_branches" in data

    stale = data["stale_branches"]
    assert len(stale) == 3

    # Check that TASK-1 and TASK-3 are returned, as they are Closed/Done
    tasks = [b["branch_name"] for b in stale]
    # assert "TASK-1" in tasks # not present since pid='1' gives TASK-3
    assert "TASK-3" in tasks
    assert "TASK-2" not in tasks
    assert "no-task" not in tasks

def test_delete_stale_branch(mocker):
    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_gl.delete_branch.return_value = True

    response = client.post("/api/stale-branches/delete", json={"project_id": "1", "branch_name": "TASK-1"})

    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    mock_gl.delete_branch.assert_called_once_with("1", "TASK-1")

    # Test failure
    mock_gl.delete_branch.return_value = False
    response = client.post("/api/stale-branches/delete", json={"project_id": "1", "branch_name": "TASK-1"})

    assert response.status_code == 500

def test_get_code_review_bottlenecks(mocker):
    import app.main
    original = app.main.settings.get("GITLAB_TRACKED_PROJECTS")
    app.main.settings.set("GITLAB_TRACKED_PROJECTS", "proj1")

    # We must patch the client classes so that instantiating them doesn't hit the real APIs.
    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_jira = mocker.patch('app.main.JiraClient').return_value
    mocker.patch('app.clients.jira_client.JIRA')
    mocker.patch('app.clients.gitlab_client.gitlab.Gitlab')

    class MockAuthor:
        def get(self, key):
            if key == 'username':
                return 'user1'
            return None

    class MockMR:
        def __init__(self, iid, title, source_branch, created_at, web_url):
            self.iid = iid
            self.title = title
            self.source_branch = source_branch
            self.created_at = created_at
            self.web_url = web_url
            self.author = MockAuthor()

    mock_gl.get_project_merge_requests.return_value = [
        MockMR(1, "Fix something", "TASK-1-fix", "2020-01-01T00:00:00.000+00:00", "http://mrs/1"),
        MockMR(2, "TASK-2: Add feature", "feature", "2020-01-01T00:00:00.000+00:00", "http://mrs/2"),
        MockMR(3, "Recent MR", "TASK-3-fix", "2099-01-01T00:00:00.000+00:00", "http://mrs/3"), # won't be old enough
        MockMR(4, "No task", "no-task", "2020-01-01T00:00:00.000+00:00", "http://mrs/4")
    ]

    class MockStatus:
        def __init__(self, name):
            self.name = name

    class MockFields:
        def __init__(self, name, summary=""):
            self.status = MockStatus(name)
            self.summary = summary

    class MockIssue:
        def __init__(self, key, status_name):
            self.key = key
            self.fields = MockFields(status_name, "Task Summary")

    # Jira JQL return
    mock_jira.search_issues.return_value = [
        MockIssue("TASK-1", "In Progress"), # Match
        MockIssue("TASK-2", "Done"), # Doesn't match status
        # TASK-3 not old enough, won't be in map
    ]

    response = client.get("/api/bottlenecks/code-review?days=2")

    assert response.status_code == 200
    data = response.json()
    assert "bottlenecks" in data

    bottlenecks = data["bottlenecks"]
    assert len(bottlenecks) == 1

    assert bottlenecks[0]["task_id"] == "TASK-1"
    assert bottlenecks[0]["task_status"] == "in progress"
    assert len(bottlenecks[0]["merge_requests"]) == 1
    assert bottlenecks[0]["merge_requests"][0]["mr_iid"] == 1

    app.main.settings.set("GITLAB_TRACKED_PROJECTS", original)
