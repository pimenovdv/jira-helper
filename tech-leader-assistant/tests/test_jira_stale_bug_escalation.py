import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

from app.tasks import jira_stale_bug_escalation_task

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.tasks.settings")
    mock.get.side_effect = lambda key, default="": {
        "OPENAI_API_KEY": "test-key",
        "JIRA_TRACKED_PROJECTS": "TEST"
    }.get(key, default)
    return mock

@pytest.fixture
def mock_jira_client(mocker):
    return mocker.patch("app.tasks.JiraClient").return_value

@pytest.fixture
def mock_llm(mocker):
    mock = mocker.patch("app.tasks.ChatOpenAI").return_value
    mock.ainvoke = mocker.AsyncMock()
    mock.ainvoke.return_value.content = "Тестовый комментарий"
    return mock

@pytest.mark.asyncio
async def test_jira_stale_bug_escalation_success(mock_settings, mock_jira_client, mock_llm):
    # Setup stale issue
    mock_issue = MagicMock()
    mock_issue.key = "TEST-123"
    mock_issue.fields.summary = "Test Bug"
    # 35 days ago
    stale_date = datetime.now(timezone.utc) - timedelta(days=35)
    mock_issue.fields.updated = stale_date.isoformat()
    mock_issue.fields.reporter.accountId = "12345"
    mock_issue.fields.assignee.accountId = "67890"

    mock_jira_client.search_issues.return_value = [mock_issue]

    # Mock comments: no existing auto-comment
    mock_comment = MagicMock()
    mock_comment.body = "Обычный комментарий"
    mock_jira_client.get_comments.return_value = [mock_comment]

    result = await jira_stale_bug_escalation_task()

    assert result == "Jira stale bug escalation task completed."
    mock_jira_client.search_issues.assert_called_once()
    mock_jira_client.get_comments.assert_called_once_with("TEST-123")
    mock_llm.ainvoke.assert_awaited_once()
    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "TEST-123"
    assert "<!-- AUTO_GENERATED_JIRA_STALE_BUG_ESCALATION -->" in args[1]
    assert "Тестовый комментарий" in args[1]

@pytest.mark.asyncio
async def test_jira_stale_bug_escalation_recent_update(mock_settings, mock_jira_client, mock_llm):
    # Setup recent issue
    mock_issue = MagicMock()
    mock_issue.key = "TEST-123"
    # 10 days ago
    recent_date = datetime.now(timezone.utc) - timedelta(days=10)
    mock_issue.fields.updated = recent_date.isoformat()

    mock_jira_client.search_issues.return_value = [mock_issue]

    result = await jira_stale_bug_escalation_task()

    assert result == "Jira stale bug escalation task completed."
    mock_jira_client.search_issues.assert_called_once()
    mock_jira_client.get_comments.assert_not_called()
    mock_llm.ainvoke.assert_not_called()
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_stale_bug_escalation_already_commented(mock_settings, mock_jira_client, mock_llm):
    # Setup stale issue
    mock_issue = MagicMock()
    mock_issue.key = "TEST-123"
    stale_date = datetime.now(timezone.utc) - timedelta(days=35)
    mock_issue.fields.updated = stale_date.isoformat()

    mock_jira_client.search_issues.return_value = [mock_issue]

    # Mock comments: existing auto-comment
    mock_comment = MagicMock()
    mock_comment.body = "<!-- AUTO_GENERATED_JIRA_STALE_BUG_ESCALATION -->\nТестовый комментарий"
    mock_jira_client.get_comments.return_value = [mock_comment]

    result = await jira_stale_bug_escalation_task()

    assert result == "Jira stale bug escalation task completed."
    mock_jira_client.search_issues.assert_called_once()
    mock_jira_client.get_comments.assert_called_once_with("TEST-123")
    mock_llm.ainvoke.assert_not_called()
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_stale_bug_escalation_no_api_key(mocker):
    mock = mocker.patch("app.tasks.settings")
    mock.get.return_value = ""

    result = await jira_stale_bug_escalation_task()

    assert result == "Jira stale bug escalation task skipped (no OpenAI API key)"
