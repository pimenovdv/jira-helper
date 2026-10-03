import pytest
from unittest.mock import MagicMock
from app.tasks import jira_unassigned_in_progress_warning_task

@pytest.fixture(autouse=True)
def mock_jira_client(mocker):
    mock = MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=mock)
    mocker.patch("app.clients.jira_client.JIRA", return_value=MagicMock())
    return mock

@pytest.fixture(autouse=True)
def mock_settings(mocker):
    mock_settings_obj = MagicMock()
    mock_settings_obj.get.return_value = "TEST"
    mocker.patch("app.tasks.settings", mock_settings_obj)
    return mock_settings_obj

@pytest.mark.asyncio
async def test_jira_unassigned_in_progress_warning_adds_comment(mock_jira_client):
    issue_mock = MagicMock()
    issue_mock.key = "TEST-1"
    issue_mock.fields.assignee = None

    mock_jira_client.search_issues.return_value = [issue_mock]
    mock_jira_client.get_issue_comments.return_value = []

    await jira_unassigned_in_progress_warning_task()

    mock_jira_client.search_issues.assert_called_once_with('project = TEST AND statusCategory = "In Progress"')
    mock_jira_client.get_issue_comments.assert_called_once_with("TEST-1")
    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "TEST-1"
    assert "<!-- AUTO_GENERATED_UNASSIGNED_IN_PROGRESS_WARNING -->" in args[1]
    assert "unassigned" in args[1]

@pytest.mark.asyncio
async def test_jira_unassigned_in_progress_warning_skips_assigned(mock_jira_client):
    issue_mock = MagicMock()
    issue_mock.key = "TEST-2"
    issue_mock.fields.assignee = "Some User"

    mock_jira_client.search_issues.return_value = [issue_mock]

    await jira_unassigned_in_progress_warning_task()

    mock_jira_client.search_issues.assert_called_once()
    mock_jira_client.get_issue_comments.assert_not_called()
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_unassigned_in_progress_warning_skips_already_commented(mock_jira_client):
    issue_mock = MagicMock()
    issue_mock.key = "TEST-3"
    issue_mock.fields.assignee = None

    comment_mock = MagicMock()
    comment_mock.body = "<!-- AUTO_GENERATED_UNASSIGNED_IN_PROGRESS_WARNING -->"

    mock_jira_client.search_issues.return_value = [issue_mock]
    mock_jira_client.get_issue_comments.return_value = [comment_mock]

    await jira_unassigned_in_progress_warning_task()

    mock_jira_client.search_issues.assert_called_once()
    mock_jira_client.get_issue_comments.assert_called_once_with("TEST-3")
    mock_jira_client.add_comment.assert_not_called()
