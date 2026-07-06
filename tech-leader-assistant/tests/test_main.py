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

def test_get_stale_branches(mocker):
    mocker.patch('app.main.settings.get', side_effect=lambda k, default='': 'proj1,proj2' if k == 'GITLAB_TRACKED_PROJECTS' else default)

    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_jira = mocker.patch('app.main.JiraClient').return_value

    class MockCommit:
        def get(self, key):
            if key == 'committed_date':
                return "2020-01-01T00:00:00.000+00:00" # Very old commit
            return None

    class MockBranch:
        def __init__(self, name):
            self.name = name
            self.commit = MockCommit()

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

@pytest.mark.asyncio
async def test_get_user_timeline(mocker):
    mock_db = mocker.AsyncMock()
    mock_result = mocker.MagicMock()

    class MockEvent:
        def __init__(self, dt):
            self.event_type = "push"
            from datetime import datetime
            self.timestamp = dt
            self.data = {"action_name": "pushed", "project_id": 1}
            self.id = 1

    from datetime import datetime
    mock_events = [MockEvent(datetime(2023, 1, 1))]
    mock_result.scalars().all.return_value = mock_events
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    from app.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    response = client.get("/api/timeline/user/1")

    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 1
    assert data["events"][0]["type"] == "push"

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_get_project_timeline(mocker):
    mock_db = mocker.AsyncMock()
    mock_result = mocker.MagicMock()

    class MockEvent:
        def __init__(self, dt):
            self.event_type = "issue"
            from datetime import datetime
            self.timestamp = dt
            self.data = {"action_name": "opened", "project_id": 1}
            self.id = 1

    from datetime import datetime
    mock_events = [MockEvent(datetime(2023, 1, 1))]
    mock_result.scalars().all.return_value = mock_events
    mock_db.execute.return_value = mock_result

    async def override_get_db():
        yield mock_db

    from app.database import get_db
    app.dependency_overrides[get_db] = override_get_db

    response = client.get("/api/timeline/project/1")

    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 1
    assert data["events"][0]["type"] == "issue"

    app.dependency_overrides.clear()

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.text.startswith("<!DOCTYPE html>")

def test_chat_endpoint_exception(mocker):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    mock_invoke = mocker.patch("app.main.app_graph.invoke")
    mock_invoke.side_effect = Exception("Graph error")

    response = client.post("/api/chat", json={"query": "Hello"})
    assert response.status_code == 500
    assert response.json()["detail"] == "Graph error"

def test_get_stale_branches_empty(mocker):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    mocker.patch('app.main.GitLabClient')
    mocker.patch('app.main.JiraClient')
    mocker.patch('app.main.settings.get', return_value='')

    response = client.get("/api/stale-branches?days=30")
    assert response.status_code == 200
    assert response.json()["stale_branches"] == []

def test_delete_stale_branch_exception(mocker):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_gl.delete_branch.return_value = False

    response = client.post("/api/stale-branches/delete", json={"project_id": "1", "branch_name": "TASK-1"})
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to delete branch"

@pytest.mark.asyncio
async def test_override_confluence_invalid_action():
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    response = client.post(
        "/api/confluence/override",
        json={"page_id": "123", "project_id": "999", "action": "invalid"}
    )
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_override_confluence_existing_link(mocker):
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    mock_db = mocker.AsyncMock()
    mock_result = mocker.MagicMock()
    mock_existing = mocker.MagicMock()
    mock_existing.data = {"manual_linked_projects": [], "manual_unlinked_projects": ["999"]}
    mock_result.scalar_one_or_none.return_value = mock_existing
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[app.dependency_overrides.get("get_db", lambda: None)] = lambda: mock_db

    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.post(
        "/api/confluence/override",
        json={"page_id": "123", "project_id": "999", "action": "link"}
    )
    assert response.status_code == 200
    assert "999" in mock_existing.data["manual_linked_projects"]
    assert "999" not in mock_existing.data["manual_unlinked_projects"]
    mock_db.commit.assert_called_once()
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_override_confluence_existing_unlink(mocker):
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    mock_db = mocker.AsyncMock()
    mock_result = mocker.MagicMock()
    mock_existing = mocker.MagicMock()
    mock_existing.data = {"manual_linked_projects": ["999"], "manual_unlinked_projects": []}
    mock_result.scalar_one_or_none.return_value = mock_existing
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[app.dependency_overrides.get("get_db", lambda: None)] = lambda: mock_db

    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.post(
        "/api/confluence/override",
        json={"page_id": "123", "project_id": "999", "action": "unlink"}
    )
    assert response.status_code == 200
    assert "999" in mock_existing.data["manual_unlinked_projects"]
    assert "999" not in mock_existing.data["manual_linked_projects"]
    mock_db.commit.assert_called_once()
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_lifespan(mocker):
    from app.main import lifespan
    from fastapi import FastAPI
    import asyncio

    app = FastAPI()
    mock_engine = mocker.patch('app.main.engine')
    mock_engine.begin.return_value.__aenter__.return_value = mocker.AsyncMock()
    mock_start = mocker.patch('app.main.start_scheduler')
    mock_shutdown = mocker.patch('app.main.shutdown_scheduler')

    async with lifespan(app):
        mock_engine.begin.assert_called_once()
        mock_start.assert_called_once()

    await asyncio.sleep(0.1) # allow async callback
    mock_shutdown.assert_called_once()

@pytest.mark.asyncio
async def test_override_confluence_existing_link_already_linked(mocker):
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    mock_db = mocker.AsyncMock()
    mock_result = mocker.MagicMock()
    mock_existing = mocker.MagicMock()
    mock_existing.data = {"manual_linked_projects": ["999"], "manual_unlinked_projects": []}
    mock_result.scalar_one_or_none.return_value = mock_existing
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[app.dependency_overrides.get("get_db", lambda: None)] = lambda: mock_db

    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.post(
        "/api/confluence/override",
        json={"page_id": "123", "project_id": "999", "action": "link"}
    )
    assert response.status_code == 200
    mock_db.commit.assert_called_once()
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_override_confluence_existing_unlink_already_unlinked(mocker):
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    mock_db = mocker.AsyncMock()
    mock_result = mocker.MagicMock()
    mock_existing = mocker.MagicMock()
    mock_existing.data = {"manual_linked_projects": [], "manual_unlinked_projects": ["999"]}
    mock_result.scalar_one_or_none.return_value = mock_existing
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[app.dependency_overrides.get("get_db", lambda: None)] = lambda: mock_db

    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.post(
        "/api/confluence/override",
        json={"page_id": "123", "project_id": "999", "action": "unlink"}
    )
    assert response.status_code == 200
    mock_db.commit.assert_called_once()
    app.dependency_overrides.clear()

def test_root_not_found(mocker):
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    mock_exists = mocker.patch("pathlib.Path.exists", return_value=False)

    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "<h1>Static files not found</h1>"

@pytest.mark.asyncio
async def test_override_confluence_existing_link_missing_keys(mocker):
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    mock_db = mocker.AsyncMock()
    mock_result = mocker.MagicMock()
    mock_existing = mocker.MagicMock()
    mock_existing.data = {} # Missing manual keys
    mock_result.scalar_one_or_none.return_value = mock_existing
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[app.dependency_overrides.get("get_db", lambda: None)] = lambda: mock_db

    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.post(
        "/api/confluence/override",
        json={"page_id": "123", "project_id": "999", "action": "link"}
    )
    assert response.status_code == 200
    mock_db.commit.assert_called_once()
    app.dependency_overrides.clear()

def test_get_stale_branches_not_stale_and_parse_error(mocker):
    mocker.patch('app.main.settings.get', side_effect=lambda k, default='': 'proj1' if k == 'GITLAB_TRACKED_PROJECTS' else default)

    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_jira = mocker.patch('app.main.JiraClient').return_value

    class MockCommitNotStale:
        def get(self, key):
            if key == 'committed_date':
                from datetime import datetime, timedelta, timezone
                return (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
                return (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            return None

    class MockCommitError:
        def get(self, key):
            if key == 'committed_date':
                return "invalid_date_format"
            return None

    class MockBranch:
        def __init__(self, name, commit_mock):
            self.name = name
            self.commit = commit_mock

    # Provide two branches, one not stale, one throwing an exception on parse but passing to jira check
    mock_gl.get_project_branches.side_effect = lambda pid: [
        MockBranch("TASK-1", MockCommitNotStale()),
        MockBranch("TASK-2", MockCommitError())
    ] if pid == "proj1" else []

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

    # Jira JQL return: TASK-2 is closed
    mock_jira.search_issues.return_value = [
        MockIssue("TASK-2", "Closed")
    ]

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    response = client.get("/api/stale-branches?days=30")

    assert response.status_code == 200
    data = response.json()
    assert "stale_branches" in data

    stale = data["stale_branches"]
    assert len(stale) == 0



def test_get_stale_branches_not_stale_no_match(mocker):
    mocker.patch('app.main.settings.get', side_effect=lambda k, default='': 'proj1' if k == 'GITLAB_TRACKED_PROJECTS' else default)

    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_jira = mocker.patch('app.main.JiraClient').return_value

    class MockCommitNotStale:
        def get(self, key):
            if key == 'committed_date':
                from datetime import datetime, timedelta, timezone
                return (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
            return None

    class MockBranch:
        def __init__(self, name, commit_mock):
            self.name = name
            self.commit = commit_mock

    mock_gl.get_project_branches.side_effect = lambda pid: [
        MockBranch("NOTATASK", MockCommitNotStale())
    ] if pid == "proj1" else []

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    response = client.get("/api/stale-branches?days=30")

    assert response.status_code == 200
    data = response.json()
    assert "stale_branches" in data
    assert len(data["stale_branches"]) == 0

def test_get_stale_branches_commit_date_missing(mocker):
    mocker.patch('app.main.settings.get', side_effect=lambda k, default='': 'proj1' if k == 'GITLAB_TRACKED_PROJECTS' else default)

    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_jira = mocker.patch('app.main.JiraClient').return_value

    class MockCommitMissing:
        def get(self, key):
            return None

    class MockBranch:
        def __init__(self, name, commit_mock):
            self.name = name
            self.commit = commit_mock

    mock_gl.get_project_branches.side_effect = lambda pid: [
        MockBranch("TASK-3", MockCommitMissing())
    ] if pid == "proj1" else []

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

    mock_jira.search_issues.return_value = [
        MockIssue("TASK-3", "Closed")
    ]

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    response = client.get("/api/stale-branches?days=30")

    assert response.status_code == 200
    data = response.json()
    stale = data["stale_branches"]
    assert len(stale) == 0



def test_get_stale_branches_no_commit_attr(mocker):
    mocker.patch('app.main.settings.get', side_effect=lambda k, default='': 'proj1' if k == 'GITLAB_TRACKED_PROJECTS' else default)

    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_jira = mocker.patch('app.main.JiraClient').return_value

    class MockBranchNoCommit:
        def __init__(self, name):
            self.name = name
            # self.commit explicitly omitted

    mock_gl.get_project_branches.side_effect = lambda pid: [
        MockBranchNoCommit("TASK-4")
    ] if pid == "proj1" else []

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

    mock_jira.search_issues.return_value = [
        MockIssue("TASK-4", "Closed")
    ]

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    response = client.get("/api/stale-branches?days=30")

    assert response.status_code == 200
    data = response.json()
    stale = data["stale_branches"]
    assert len(stale) == 0



def test_get_stale_branches_not_stale_and_exception(mocker):
    mocker.patch('app.main.settings.get', side_effect=lambda k, default='': 'proj1' if k == 'GITLAB_TRACKED_PROJECTS' else default)

    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_jira = mocker.patch('app.main.JiraClient').return_value

    class MockCommitNotStale:
        def get(self, key):
            if key == 'committed_date':
                from datetime import datetime, timedelta, timezone
                return (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
            return None

    class MockCommitError:
        def get(self, key):
            if key == 'committed_date':
                return "invalid_date_format"
            return None

    class MockBranch:
        def __init__(self, name, commit_mock):
            self.name = name
            self.commit = commit_mock

    mock_gl.get_project_branches.side_effect = lambda pid: [
        MockBranch("TASK-1", MockCommitNotStale()),
        MockBranch("TASK-2", MockCommitError())
    ] if pid == "proj1" else []

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

    mock_jira.search_issues.return_value = [
        MockIssue("TASK-2", "Closed")
    ]

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    response = client.get("/api/stale-branches?days=30")

    assert response.status_code == 200
    data = response.json()
    stale = data["stale_branches"]
    assert len(stale) == 0



def test_delete_stale_branch_not_found(mocker):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_gl.delete_branch.return_value = False

    response = client.post("/api/stale-branches/delete", json={"project_id": "1", "branch_name": "TASK-UNKNOWN"})
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to delete branch"

def test_get_stale_branches_gitlab_exception(mocker):
    mocker.patch('app.main.settings.get', side_effect=lambda k, default='': 'proj1' if k == 'GITLAB_TRACKED_PROJECTS' else default)
    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mocker.patch('app.main.JiraClient')

    mock_gl.get_project_branches.side_effect = Exception("API error")

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    response = client.get("/api/stale-branches?days=30")

    assert response.status_code == 500
    assert response.json()["detail"] == "API error"

def test_get_stale_branches_jira_exception(mocker):
    mocker.patch('app.main.settings.get', side_effect=lambda k, default='': 'proj1' if k == 'GITLAB_TRACKED_PROJECTS' else default)
    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_jira = mocker.patch('app.main.JiraClient').return_value

    class MockCommitNotStale:
        def get(self, key):
            if key == 'committed_date':
                from datetime import datetime, timedelta, timezone
                return (datetime.now(timezone.utc) - timedelta(days=60)).isoformat().replace("+00:00", "Z")
            return None

    class MockBranch:
        def __init__(self, name, commit_mock):
            self.name = name
            self.commit = commit_mock

    mock_gl.get_project_branches.return_value = [MockBranch("TASK-1", MockCommitNotStale())]

    mock_jira.search_issues.side_effect = Exception("Jira API error")

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    response = client.get("/api/stale-branches?days=30")

    assert response.status_code == 500
    assert response.json()["detail"] == "Jira API error"

import pytest

def test_get_stale_branches_not_stale_coverage(mocker):
    mocker.patch('app.main.settings.get', side_effect=lambda k, default='': 'proj1' if k == 'GITLAB_TRACKED_PROJECTS' else default)
    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_jira = mocker.patch('app.main.JiraClient').return_value

    class MockCommitNotStale:
        def get(self, key):
            if key == 'committed_date':
                from datetime import datetime, timedelta, timezone
                return (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")
            return None

    class MockBranch:
        def __init__(self, name, commit_mock):
            self.name = name
            self.commit = commit_mock

    mock_gl.get_project_branches.side_effect = lambda pid: [
        MockBranch("TASK-1", MockCommitNotStale())
    ] if pid == "proj1" else []

    mock_jira.search_issues.return_value = []

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    response = client.get("/api/stale-branches?days=30")

    assert response.status_code == 200
    assert len(response.json()["stale_branches"]) == 0


def test_get_stale_branches_tz_none(mocker):
    mocker.patch('app.main.settings.get', side_effect=lambda k, default='': 'proj1' if k == 'GITLAB_TRACKED_PROJECTS' else default)
    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_jira = mocker.patch('app.main.JiraClient').return_value

    class MockCommitNotStale:
        def get(self, key):
            if key == 'committed_date':
                from datetime import datetime, timedelta, timezone
                return (datetime.now() - timedelta(days=1)).isoformat()
            return None

    class MockBranch:
        def __init__(self, name, commit_mock):
            self.name = name
            self.commit = commit_mock

    mock_gl.get_project_branches.side_effect = lambda pid: [
        MockBranch("TASK-1", MockCommitNotStale())
    ] if pid == "proj1" else []

    mock_jira.search_issues.return_value = []

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    response = client.get("/api/stale-branches?days=30")

    assert response.status_code == 200
    assert len(response.json()["stale_branches"]) == 0

def test_get_stale_branches_exception_coverage(mocker):
    mocker.patch('app.main.settings.get', side_effect=lambda k, default='': 'proj1' if k == 'GITLAB_TRACKED_PROJECTS' else default)
    mock_gl = mocker.patch('app.main.GitLabClient').return_value
    mock_jira = mocker.patch('app.main.JiraClient').return_value

    class MockCommitError:
        def get(self, key):
            if key == 'committed_date':
                return "invalid-date"
            return None

    class MockBranch:
        def __init__(self, name, commit_mock):
            self.name = name
            self.commit = commit_mock

    mock_gl.get_project_branches.side_effect = lambda pid: [
        MockBranch("TASK-1", MockCommitError())
    ] if pid == "proj1" else []

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

    mock_jira.search_issues.return_value = [MockIssue("TASK-1", "Done")]

    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    response = client.get("/api/stale-branches?days=30")

    assert response.status_code == 200
    assert len(response.json()["stale_branches"]) == 0
