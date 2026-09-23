import pytest
from unittest.mock import MagicMock
from app.tasks import jira_stale_active_sprint_issue_warning_task

@pytest.fixture
def mock_jira_client(mocker):
    mock_module = mocker.patch("app.clients.jira_client.JiraClient")
    mock_instance = mock_module.return_value
    return mock_instance

@pytest.mark.asyncio
async def test_no_issues(mock_jira_client):
    mock_jira_client.search_issues.return_value = []

    result = await jira_stale_active_sprint_issue_warning_task()

    assert result == "No stale active sprint issues found"
    mock_jira_client.search_issues.assert_called_once_with("sprint in openSprints() AND resolution = Unresolved AND updated <= -2d")
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_issue_already_warned(mock_jira_client):
    issue = MagicMock()
    issue.key = "TASK-1"

    comment = MagicMock()
    comment.body = "Warning <!-- AUTO_GENERATED_STALE_ACTIVE_SPRINT_WARNING -->"

    mock_jira_client.search_issues.return_value = [issue]
    mock_jira_client.get_comments.return_value = [comment]

    result = await jira_stale_active_sprint_issue_warning_task()

    assert "warned 0 issues" in result
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_issue_not_warned_adds_comment(mock_jira_client):
    issue = MagicMock()
    issue.key = "TASK-2"
    issue.fields = MagicMock()
    issue.fields.assignee = MagicMock()
    issue.fields.assignee.accountId = "12345"

    comment = MagicMock()
    comment.body = "Some regular comment"

    mock_jira_client.search_issues.return_value = [issue]
    mock_jira_client.get_comments.return_value = [comment]

    result = await jira_stale_active_sprint_issue_warning_task()

    assert "warned 1 issues" in result
    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "TASK-2"
    assert "<!-- AUTO_GENERATED_STALE_ACTIVE_SPRINT_WARNING -->" in args[1]
    assert "[~accountid:12345]" in args[1]

@pytest.mark.asyncio
async def test_issue_unassigned_adds_comment(mock_jira_client):
    issue = MagicMock()
    issue.key = "TASK-3"
    issue.fields = MagicMock()
    issue.fields.assignee = None

    mock_jira_client.search_issues.return_value = [issue]
    mock_jira_client.get_comments.return_value = []

    result = await jira_stale_active_sprint_issue_warning_task()

    assert "warned 1 issues" in result
    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "TASK-3"
    assert "Hello Assignee" in args[1]

@pytest.mark.asyncio
async def test_handles_exception(mock_jira_client):
    issue = MagicMock()
    issue.key = "TASK-4"

    mock_jira_client.search_issues.return_value = [issue]
    mock_jira_client.get_comments.side_effect = Exception("Test exception")

    result = await jira_stale_active_sprint_issue_warning_task()

    assert "warned 0 issues" in result
    mock_jira_client.add_comment.assert_not_called()
