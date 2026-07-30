import pytest
from unittest.mock import MagicMock
from app.tasks import jira_overdue_task_reminder_task
from datetime import datetime, timedelta, timezone

@pytest.fixture
def mock_jira_client(mocker):
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = "JIRA-PROJ"

    mock_jira_client_cls = mocker.patch("app.tasks.JiraClient")
    mock_client_instance = mock_jira_client_cls.return_value

    return mock_client_instance


@pytest.mark.asyncio
async def test_jira_overdue_task_reminder_task_sends_reminder(mock_jira_client):
    mock_issue = MagicMock()
    mock_issue.key = "JIRA-123"

    # Date in the past
    past_date = datetime.now(timezone.utc) - timedelta(days=2)
    mock_issue.fields.duedate = past_date.isoformat()

    mock_jira_client.search_issues.return_value = [mock_issue]
    mock_jira_client.get_comments.return_value = []

    await jira_overdue_task_reminder_task()

    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "JIRA-123"
    assert "<!-- AUTO_GENERATED_OVERDUE_REMINDER -->" in args[1]

@pytest.mark.asyncio
async def test_jira_overdue_task_reminder_task_already_reminded(mock_jira_client):
    mock_issue = MagicMock()
    mock_issue.key = "JIRA-456"

    past_date = datetime.now(timezone.utc) - timedelta(days=2)
    mock_issue.fields.duedate = past_date.isoformat()

    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "already done <!-- AUTO_GENERATED_OVERDUE_REMINDER -->"
    mock_jira_client.get_comments.return_value = [mock_comment]

    await jira_overdue_task_reminder_task()

    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_overdue_task_reminder_task_not_overdue(mock_jira_client):
    mock_issue = MagicMock()
    mock_issue.key = "JIRA-789"

    # Date in the future
    future_date = datetime.now(timezone.utc) + timedelta(days=2)
    mock_issue.fields.duedate = future_date.isoformat()

    mock_jira_client.search_issues.return_value = [mock_issue]
    mock_jira_client.get_comments.return_value = []

    await jira_overdue_task_reminder_task()

    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_overdue_task_reminder_task_no_duedate(mock_jira_client):
    mock_issue = MagicMock()
    mock_issue.key = "JIRA-101"

    # No due date
    mock_issue.fields.duedate = None

    mock_jira_client.search_issues.return_value = [mock_issue]
    mock_jira_client.get_comments.return_value = []

    await jira_overdue_task_reminder_task()

    mock_jira_client.add_comment.assert_not_called()
