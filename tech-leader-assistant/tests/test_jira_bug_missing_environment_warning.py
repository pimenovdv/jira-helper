import pytest
from unittest.mock import MagicMock
from app.tasks import jira_bug_missing_environment_warning_task

@pytest.fixture(autouse=True)
def mock_jira_client_init(mocker):
    # Mock JIRA client initialization to avoid real connection attempts during tests
    return mocker.patch('app.clients.jira_client.JIRA')

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.tasks.settings")
    mock.get.side_effect = lambda key, default="": {
        "JIRA_TRACKED_PROJECTS": "PROJ1",
    }.get(key, default)
    # Also patch clients settings
    mocker.patch("app.clients.jira_client.settings", mock)
    mocker.patch("app.clients.settings", mock)
    return mock

@pytest.fixture
def mock_jira_client_class(mocker):
    return mocker.patch("app.tasks.JiraClient")


@pytest.mark.asyncio
async def test_jira_bug_missing_environment_warning_task_no_env_no_comment(mocker, mock_settings, mock_jira_client_class):
    mock_jira = mock_jira_client_class.return_value

    # Mock issue
    mock_issue = MagicMock()
    mock_issue.key = "BUG-1"
    mock_issue.fields.environment = None

    mock_jira.search_issues.return_value = [mock_issue]
    mock_jira.get_comments.return_value = []

    # Run the task
    result = await jira_bug_missing_environment_warning_task()

    # Assertions
    mock_jira.search_issues.assert_called_once_with('issuetype = Bug AND statusCategory != Done')
    mock_jira.get_comments.assert_called_once_with("BUG-1")
    mock_jira.add_comment.assert_called_once()
    args, _ = mock_jira.add_comment.call_args
    assert args[0] == "BUG-1"
    assert "Please provide the environment details" in args[1]
    assert "Warned 1 issues" in result

@pytest.mark.asyncio
async def test_jira_bug_missing_environment_warning_task_has_env(mocker, mock_settings, mock_jira_client_class):
    mock_jira = mock_jira_client_class.return_value

    # Mock issue with environment
    mock_issue = MagicMock()
    mock_issue.key = "BUG-2"
    mock_issue.fields.environment = "Production - Safari"

    mock_jira.search_issues.return_value = [mock_issue]

    # Run the task
    result = await jira_bug_missing_environment_warning_task()

    # Assertions
    mock_jira.search_issues.assert_called_once()
    mock_jira.get_comments.assert_not_called()
    mock_jira.add_comment.assert_not_called()
    assert "Warned 0 issues" in result

@pytest.mark.asyncio
async def test_jira_bug_missing_environment_warning_task_already_commented(mocker, mock_settings, mock_jira_client_class):
    mock_jira = mock_jira_client_class.return_value

    # Mock issue with no environment
    mock_issue = MagicMock()
    mock_issue.key = "BUG-3"
    mock_issue.fields.environment = None

    mock_jira.search_issues.return_value = [mock_issue]

    # Mock existing bot comment
    mock_comment = MagicMock()
    if isinstance(mock_comment, MagicMock):
         mock_comment.get.return_value = "Hello! This bug appears to be missing environment details. Please provide the environment details (e.g., OS, browser, app version) to help developers reproduce and fix the issue."
    mock_comment.body = "Hello! This bug appears to be missing environment details. Please provide the environment details (e.g., OS, browser, app version) to help developers reproduce and fix the issue."
    mock_jira.get_comments.return_value = [mock_comment]

    # Run the task
    result = await jira_bug_missing_environment_warning_task()

    # Assertions
    mock_jira.search_issues.assert_called_once()
    mock_jira.get_comments.assert_called_once_with("BUG-3")
    mock_jira.add_comment.assert_not_called()
    assert "Warned 0 issues" in result
