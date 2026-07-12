import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.clients import settings

client = TestClient(app)

@pytest.fixture(autouse=True)
def restore_settings():
    orig_jira = settings.get("JIRA_TRACKED_PROJECTS")
    orig_gitlab = settings.get("GITLAB_TRACKED_PROJECTS")
    yield
    settings.set("JIRA_TRACKED_PROJECTS", orig_jira)
    settings.set("GITLAB_TRACKED_PROJECTS", orig_gitlab)



class MockIssue:
    def __init__(self, key, summary, created_str, resolved_str):
        self.key = key
        self.fields = MagicMock()
        self.fields.summary = summary
        self.fields.created = created_str
        self.fields.resolutiondate = resolved_str

class MockBranch:
    def __init__(self, name):
        self.name = name

class MockCommit:
    def __init__(self, message):
        self.message = message

class MockMR:
    def __init__(self, title, source_branch):
        self.title = title
        self.source_branch = source_branch

@pytest.fixture
def mock_clients(mocker):
    mock_jira = mocker.patch("app.main.JiraClient")
    mock_gitlab = mocker.patch("app.main.GitLabClient")
    mock_confluence = mocker.patch("app.main.ConfluenceClient")

    jira_instance = mock_jira.return_value
    jira_instance.search_issues.return_value = []

    gitlab_instance = mock_gitlab.return_value
    gitlab_instance.get_project_branches.return_value = []
    gitlab_instance.get_project_commits.return_value = []
    gitlab_instance.get_project_merge_requests.return_value = []

    confluence_instance = mock_confluence.return_value
    confluence_instance.search_cql.return_value = {"results": []}
    confluence_instance.url = "http://confluence"

    return {
        "jira": jira_instance,
        "gitlab": gitlab_instance,
        "confluence": confluence_instance
    }

def test_developer_velocity_no_projects(mock_clients):
    settings.set("JIRA_TRACKED_PROJECTS", "")

    response = client.get("/api/metrics/developer-velocity")
    assert response.status_code == 200
    assert response.json() == {"velocity_metrics": []}

def test_developer_velocity_normal(mock_clients):
    settings.set("JIRA_TRACKED_PROJECTS", "PROJ")
    settings.set("GITLAB_TRACKED_PROJECTS", "123")

    issue = MockIssue("PROJ-1", "Fast task", "2023-10-10T12:00:00.000+0000", "2023-10-11T12:00:00.000+0000")
    mock_clients["jira"].search_issues.return_value = [issue]

    mock_clients["gitlab"].get_project_branches.return_value = [MockBranch("feature/PROJ-1-test")]
    mock_clients["gitlab"].get_project_commits.return_value = [MockCommit("fix")]
    mock_clients["gitlab"].get_project_merge_requests.return_value = [MockMR("Implement PROJ-1", "feature/PROJ-1-test")]

    response = client.get("/api/metrics/developer-velocity")
    assert response.status_code == 200
    data = response.json()["velocity_metrics"]
    assert len(data) == 1

    assert data[0]["task_id"] == "PROJ-1"
    assert data[0]["completion_time_days"] == 1
    assert data[0]["mr_count"] == 1
    assert data[0]["commit_count"] == 1
    assert data[0]["is_low_velocity"] is False
    assert len(data[0]["possible_causes"]) == 0

def test_developer_velocity_low(mock_clients):
    settings.set("JIRA_TRACKED_PROJECTS", "PROJ")
    settings.set("GITLAB_TRACKED_PROJECTS", "123")

    # > 5 days (10 days)
    issue = MockIssue("PROJ-2", "Slow task", "2023-10-10T12:00:00.000+0000", "2023-10-20T12:00:00.000+0000")
    mock_clients["jira"].search_issues.return_value = [issue]

    mock_clients["gitlab"].get_project_branches.return_value = []
    mock_clients["gitlab"].get_project_commits.return_value = []
    mock_clients["gitlab"].get_project_merge_requests.return_value = []

    mock_clients["confluence"].search_cql.return_value = {
        "results": [{"title": "Meeting notes PROJ-2", "_links": {"webui": "/display/SPACE/notes"}}]
    }

    response = client.get("/api/metrics/developer-velocity")
    assert response.status_code == 200
    data = response.json()["velocity_metrics"]
    assert len(data) == 1

    assert data[0]["task_id"] == "PROJ-2"
    assert data[0]["completion_time_days"] == 10
    assert data[0]["is_low_velocity"] is True
    assert len(data[0]["possible_causes"]) == 1
    assert data[0]["possible_causes"][0]["title"] == "Meeting notes PROJ-2"
    assert data[0]["possible_causes"][0]["url"] == "http://confluence/display/SPACE/notes"

def test_developer_velocity_no_ms_date(mock_clients):
    settings.set("JIRA_TRACKED_PROJECTS", "PROJ")
    settings.set("GITLAB_TRACKED_PROJECTS", "123")

    issue = MockIssue("PROJ-3", "Task no ms", "2023-10-10T12:00:00+0000", "2023-10-12T12:00:00+0000")
    mock_clients["jira"].search_issues.return_value = [issue]

    response = client.get("/api/metrics/developer-velocity")
    assert response.status_code == 200
    data = response.json()["velocity_metrics"]
    assert len(data) == 1

    assert data[0]["completion_time_days"] == 2

def test_developer_velocity_missing_dates(mock_clients):
    settings.set("JIRA_TRACKED_PROJECTS", "PROJ")
    settings.set("GITLAB_TRACKED_PROJECTS", "123")

    issue = MockIssue("PROJ-4", "Missing date task", None, None)
    mock_clients["jira"].search_issues.return_value = [issue]

    response = client.get("/api/metrics/developer-velocity")
    assert response.status_code == 200
    data = response.json()["velocity_metrics"]
    assert len(data) == 1

    assert data[0]["completion_time_days"] == 0

def test_developer_velocity_exception(mock_clients):
    mock_clients["jira"].search_issues.side_effect = Exception("Jira failure")

    response = client.get("/api/metrics/developer-velocity")
    assert response.status_code == 500
    assert "Jira failure" in response.json()["detail"]
