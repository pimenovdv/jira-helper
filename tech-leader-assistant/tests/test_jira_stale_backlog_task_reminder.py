import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
from app.tasks import jira_stale_backlog_task_reminder_task

@pytest.fixture
def mock_settings(mocker):
    mock_s = MagicMock()
    mock_s.get.side_effect = lambda k, default="": {
        "JIRA_STALE_BACKLOG_DAYS": "90"
    }.get(k, default)
    mocker.patch("app.tasks.settings", mock_s)
    mocker.patch("app.clients.settings", mock_s)
    mocker.patch("app.clients.jira_client.settings", mock_s)
    return mock_s

@pytest.fixture(autouse=True)
def mock_jira_lib(mocker):
    return mocker.patch("app.clients.jira_client.JIRA")

@pytest.fixture
def mock_jira_client(mocker):
    # This must mock JiraClient inside app.tasks where it's being used
    mock_jc_class = mocker.patch("app.tasks.JiraClient")
    mock_instance = MagicMock()
    mock_jc_class.return_value = mock_instance

    # Also patch it inside tasks where it imports locally if needed
    # Actually, the tasks does: from app.clients.jira_client import JiraClient
    mocker.patch("app.clients.jira_client.JiraClient", return_value=mock_instance)
    return mock_instance

@pytest.mark.asyncio
async def test_jira_stale_backlog_reminder_posts_comment(mock_settings, mock_jira_client):
    now = datetime.now(timezone.utc)
    old_date = (now - timedelta(days=100)).isoformat()

    mock_issue = MagicMock()
    mock_issue.key = "PROJ-123"
    mock_issue.fields.updated = old_date

    mock_jira_client.search_issues.return_value = [mock_issue]

    # No existing comments
    mock_jira_client.get_issue_comments.return_value = []

    res = await jira_stale_backlog_task_reminder_task()

    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "PROJ-123"
    assert "This issue has been in the backlog/to do list and inactive for" in args[1]
    assert "<!-- AUTO_GENERATED_STALE_BACKLOG_REMINDER -->" in args[1]
    assert "warned 1 issues" in res

@pytest.mark.asyncio
async def test_jira_stale_backlog_reminder_skips_already_reminded(mock_settings, mock_jira_client):
    now = datetime.now(timezone.utc)
    old_date = (now - timedelta(days=100)).isoformat()

    mock_issue = MagicMock()
    mock_issue.key = "PROJ-123"
    mock_issue.fields.updated = old_date

    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "<!-- AUTO_GENERATED_STALE_BACKLOG_REMINDER -->"
    mock_jira_client.get_issue_comments.return_value = [mock_comment]

    res = await jira_stale_backlog_task_reminder_task()

    mock_jira_client.add_comment.assert_not_called()
    assert "warned 0 issues" in res

@pytest.mark.asyncio
async def test_jira_stale_backlog_reminder_no_issues(mock_settings, mock_jira_client):
    mock_jira_client.search_issues.return_value = []

    res = await jira_stale_backlog_task_reminder_task()

    mock_jira_client.add_comment.assert_not_called()
    assert "warned 0 issues" in res
