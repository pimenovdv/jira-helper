import pytest
from unittest.mock import AsyncMock, MagicMock
from app.tasks import jira_blocked_issue_followup_reminder_task

@pytest.fixture(autouse=True)
def mock_jira_client_init(mocker):
    # Prevent Jira client from connecting during init
    mocker.patch("app.clients.jira_client.JIRA")

@pytest.mark.asyncio
async def test_jira_blocked_issue_followup_reminder_task(mocker):
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.side_effect = lambda key, default="": {
        "OPENAI_API_KEY": "test_openai_key",
        "JIRA_TRACKED_PROJECTS": "TEST"
    }.get(key, default)

    mock_chat_openai = mocker.patch("app.tasks.ChatOpenAI")
    mock_llm_instance = AsyncMock()
    mock_chat_openai.return_value = mock_llm_instance
    mock_response = MagicMock()
    mock_response.content = "Тестовое сообщение"
    mock_llm_instance.ainvoke.return_value = mock_response

    mock_jira_client_class = mocker.patch("app.tasks.JiraClient")
    mock_jira_client = MagicMock()
    mock_jira_client_class.return_value = mock_jira_client

    mock_issue = MagicMock()
    mock_issue.key = "TEST-123"
    mock_issue.fields.assignee = MagicMock()
    mock_issue.fields.assignee.accountId = "user123"
    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "Some comment"
    mock_jira_client.get_comments.return_value = [mock_comment]

    await jira_blocked_issue_followup_reminder_task()

    mock_jira_client.search_issues.assert_called_once_with('project = "TEST" AND status = "Blocked" AND updated <= -5d AND assignee is not EMPTY')
    mock_llm_instance.ainvoke.assert_awaited_once()
    assert "Тестовое сообщение" in mock_jira_client.add_comment.call_args[0][1]
    assert "<!-- AUTO_GENERATED_JIRA_BLOCKED_FOLLOWUP_REMINDER -->" in mock_jira_client.add_comment.call_args[0][1]

@pytest.mark.asyncio
async def test_jira_blocked_issue_followup_reminder_task_already_reminded(mocker):
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.side_effect = lambda key, default="": {
        "OPENAI_API_KEY": "test_openai_key",
        "JIRA_TRACKED_PROJECTS": "TEST"
    }.get(key, default)

    mock_chat_openai = mocker.patch("app.tasks.ChatOpenAI")

    mock_jira_client_class = mocker.patch("app.tasks.JiraClient")
    mock_jira_client = MagicMock()
    mock_jira_client_class.return_value = mock_jira_client

    mock_issue = MagicMock()
    mock_issue.key = "TEST-123"
    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "Some comment <!-- AUTO_GENERATED_JIRA_BLOCKED_FOLLOWUP_REMINDER -->"
    mock_jira_client.get_comments.return_value = [mock_comment]

    await jira_blocked_issue_followup_reminder_task()

    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_blocked_issue_followup_reminder_task_no_api_key(mocker):
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = ""

    mock_chat_openai = mocker.patch("app.tasks.ChatOpenAI")

    await jira_blocked_issue_followup_reminder_task()

    mock_chat_openai.assert_not_called()
