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
    def __init__(self, key, summary):
        self.key = key
        self.fields = MagicMock()
        self.fields.summary = summary

class MockBranch:
    def __init__(self, name):
        self.name = name

class MockCommit:
    def __init__(self, message):
        self.message = message

@pytest.fixture
def mock_clients(mocker):
    mock_jira = mocker.patch("app.main.JiraClient")
    mock_gitlab = mocker.patch("app.main.GitLabClient")
    mock_confluence = mocker.patch("app.main.ConfluenceClient")

    # Setup standard mock responses
    jira_instance = mock_jira.return_value
    jira_instance.search_issues.return_value = []

    gitlab_instance = mock_gitlab.return_value
    gitlab_instance.get_project_branches.return_value = []
    gitlab_instance.get_project_commits.return_value = []

    confluence_instance = mock_confluence.return_value
    confluence_instance.search_cql.return_value = {"results": []}

    return {
        "jira": jira_instance,
        "gitlab": gitlab_instance,
        "confluence": confluence_instance
    }

def test_gap_analysis_no_projects(mock_clients):
    settings.set("JIRA_TRACKED_PROJECTS", "")

    response = client.get("/api/debt/gap-analysis")
    assert response.status_code == 200
    assert response.json() == {"debt_tasks": []}

def test_gap_analysis_fully_covered(mock_clients):
    settings.set("JIRA_TRACKED_PROJECTS", "PROJ")
    settings.set("GITLAB_TRACKED_PROJECTS", "123")

    issue = MockIssue("PROJ-1", "A fully covered task")
    mock_clients["jira"].search_issues.return_value = [issue]

    branch = MockBranch("feature/PROJ-1-test")
    mock_clients["gitlab"].get_project_branches.return_value = [branch]

    commit = MockCommit("add unit test for PROJ-1")
    mock_clients["gitlab"].get_project_commits.return_value = [commit]

    mock_clients["confluence"].search_cql.return_value = {"results": [{"id": "1", "title": "PROJ-1 Docs"}]}

    response = client.get("/api/debt/gap-analysis")
    assert response.status_code == 200
    assert response.json() == {"debt_tasks": []}

def test_gap_analysis_missing_tests(mock_clients):
    settings.set("JIRA_TRACKED_PROJECTS", "PROJ")
    settings.set("GITLAB_TRACKED_PROJECTS", "123")

    issue = MockIssue("PROJ-2", "Task missing tests")
    mock_clients["jira"].search_issues.return_value = [issue]

    branch = MockBranch("feature/PROJ-2-impl")
    mock_clients["gitlab"].get_project_branches.return_value = [branch]

    commit = MockCommit("implemented feature")
    mock_clients["gitlab"].get_project_commits.return_value = [commit]

    mock_clients["confluence"].search_cql.return_value = {"results": [{"id": "2", "title": "PROJ-2 Docs"}]}

    response = client.get("/api/debt/gap-analysis")
    assert response.status_code == 200
    assert len(response.json()["debt_tasks"]) == 1

    task = response.json()["debt_tasks"][0]
    assert task["task_id"] == "PROJ-2"
    assert task["missing_tests"] is True
    assert task["missing_docs"] is False

def test_gap_analysis_missing_docs(mock_clients):
    settings.set("JIRA_TRACKED_PROJECTS", "PROJ")
    settings.set("GITLAB_TRACKED_PROJECTS", "123")

    issue = MockIssue("PROJ-3", "Task missing docs")
    mock_clients["jira"].search_issues.return_value = [issue]

    branch = MockBranch("feature/PROJ-3-test")
    mock_clients["gitlab"].get_project_branches.return_value = [branch]

    commit = MockCommit("add test for PROJ-3")
    mock_clients["gitlab"].get_project_commits.return_value = [commit]

    mock_clients["confluence"].search_cql.return_value = {"results": []}

    response = client.get("/api/debt/gap-analysis")
    assert response.status_code == 200
    assert len(response.json()["debt_tasks"]) == 1

    task = response.json()["debt_tasks"][0]
    assert task["task_id"] == "PROJ-3"
    assert task["missing_tests"] is False
    assert task["missing_docs"] is True

def test_gap_analysis_missing_both(mock_clients):
    settings.set("JIRA_TRACKED_PROJECTS", "PROJ")
    settings.set("GITLAB_TRACKED_PROJECTS", "123")

    issue = MockIssue("PROJ-4", "Task missing both")
    mock_clients["jira"].search_issues.return_value = [issue]

    mock_clients["gitlab"].get_project_branches.return_value = []
    mock_clients["confluence"].search_cql.return_value = {"results": []}

    response = client.get("/api/debt/gap-analysis")
    assert response.status_code == 200
    assert len(response.json()["debt_tasks"]) == 1

    task = response.json()["debt_tasks"][0]
    assert task["task_id"] == "PROJ-4"
    assert task["missing_tests"] is True
    assert task["missing_docs"] is True

def test_gap_analysis_jira_error(mock_clients):
    settings.set("JIRA_TRACKED_PROJECTS", "PROJ")
    mock_clients["jira"].search_issues.side_effect = Exception("Jira error")

    response = client.get("/api/debt/gap-analysis")
    assert response.status_code == 500
    assert "Jira error" in response.json()["detail"]
