import pytest
from unittest.mock import MagicMock
from app.tasks import jira_bug_missing_affected_version_warning_task

@pytest.fixture(autouse=True)
def mock_jira_base(mocker):
    # Mock the underlying JIRA package to prevent any actual network calls
    mocker.patch("app.clients.jira_client.JIRA", autospec=True)

@pytest.fixture
def mock_settings(mocker):
    mock_set = mocker.patch("app.tasks.settings")
    mock_set.get.side_effect = lambda key, default="": {
        "JIRA_TRACKED_PROJECTS": "TEST-PROJ",
    }.get(key, default)
    # Also patch clients settings
    mocker.patch("app.clients.settings", mock_set)
    return mock_set

@pytest.fixture
def mock_settings_no_proj(mocker):
    mock_set = mocker.patch("app.tasks.settings")
    mock_set.get.return_value = ""
    mocker.patch("app.clients.settings", mock_set)
    return mock_set

@pytest.fixture
def mock_jira_client(mocker):
    mock_client = mocker.patch("app.clients.jira_client.JiraClient")
    instance = mock_client.return_value
    return instance

@pytest.mark.asyncio
async def test_jira_bug_missing_affected_version_warning_task_no_project(mock_settings_no_proj, mock_jira_client):
    res = await jira_bug_missing_affected_version_warning_task()
    assert "No tracked projects" in res
    mock_jira_client.search_issues.assert_not_called()

@pytest.mark.asyncio
async def test_jira_bug_missing_affected_version_warning_task_with_versions(mock_settings, mock_jira_client):
    issue_with_versions = MagicMock()
    issue_with_versions.key = "TEST-1"
    issue_with_versions.fields.versions = [{"name": "1.0.0"}]

    mock_jira_client.search_issues.return_value = [issue_with_versions]

    res = await jira_bug_missing_affected_version_warning_task()
    assert "Warned 0 bugs" in res
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_bug_missing_affected_version_warning_task_already_warned(mock_settings, mock_jira_client):
    issue_without_versions = MagicMock()
    issue_without_versions.key = "TEST-2"
    issue_without_versions.fields.versions = []

    mock_jira_client.search_issues.return_value = [issue_without_versions]

    comment = MagicMock()
    comment.body = "<!-- AUTO_GENERATED_BUG_MISSING_AFFECTED_VERSION_WARNING -->\nWarning"
    mock_jira_client.get_comments.return_value = [comment]

    res = await jira_bug_missing_affected_version_warning_task()
    assert "Warned 0 bugs" in res
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_bug_missing_affected_version_warning_task_success(mock_settings, mock_jira_client):
    issue_without_versions = MagicMock()
    issue_without_versions.key = "TEST-3"
    issue_without_versions.fields.versions = []

    mock_jira_client.search_issues.return_value = [issue_without_versions]
    mock_jira_client.get_comments.return_value = []

    res = await jira_bug_missing_affected_version_warning_task()
    assert "Warned 1 bugs" in res
    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "TEST-3"
    assert "Missing Affected Version Warning" in args[1]
    assert "AUTO_GENERATED_BUG_MISSING_AFFECTED_VERSION_WARNING" in args[1]
