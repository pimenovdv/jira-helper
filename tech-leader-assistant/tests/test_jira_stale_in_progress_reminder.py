import pytest
from unittest.mock import MagicMock
from app.tasks import jira_stale_in_progress_reminder_task

@pytest.mark.asyncio
async def test_jira_stale_in_progress_reminder_no_api_key(mocker):
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.side_effect = lambda k, d="": "" if k == "OPENAI_API_KEY" else d

    result = await jira_stale_in_progress_reminder_task()
    assert "skipped (no OpenAI API key)" in result

@pytest.mark.asyncio
async def test_jira_stale_in_progress_reminder_success(mocker):
    # Mock settings
    mock_settings = mocker.patch("app.tasks.settings")
    def settings_get(key, default=""):
        if key == "OPENAI_API_KEY":
            return "fake_key"
        if key == "JIRA_TRACKED_PROJECTS":
            return "TESTPROJ"
        return default
    mock_settings.get.side_effect = settings_get

    # Mock ChatOpenAI
    mock_chat = mocker.patch("app.tasks.ChatOpenAI")
    mock_llm_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Reminder comment <!-- AUTO_GENERATED_JIRA_STALE_IN_PROGRESS_REMINDER -->"
    mock_llm_instance.invoke.return_value = mock_response
    mock_chat.return_value = mock_llm_instance

    # Mock JiraClient
    mock_jira_client_class = mocker.patch("app.tasks.JiraClient")
    mock_jira = MagicMock()
    mock_jira_client_class.return_value = mock_jira

    # Fake issue
    fake_issue = MagicMock()
    fake_issue.key = "TESTPROJ-123"
    fake_issue.fields.assignee.displayName = "Test User"

    mock_jira.search_issues.return_value = [fake_issue]

    # Fake comments (no marker)
    fake_comment = MagicMock()
    fake_comment.body = "Some regular comment"
    mock_jira.get_comments.return_value = [fake_comment]

    result = await jira_stale_in_progress_reminder_task()

    assert "completed" in result
    mock_jira.search_issues.assert_called_once_with('project = "TESTPROJ" AND status = "In Progress" AND updated <= -5d')
    mock_jira.get_comments.assert_called_once_with("TESTPROJ-123")
    mock_jira.add_comment.assert_called_once_with("TESTPROJ-123", "Reminder comment <!-- AUTO_GENERATED_JIRA_STALE_IN_PROGRESS_REMINDER -->")

@pytest.mark.asyncio
async def test_jira_stale_in_progress_reminder_already_reminded(mocker):
    # Mock settings
    mock_settings = mocker.patch("app.tasks.settings")
    def settings_get(key, default=""):
        if key == "OPENAI_API_KEY":
            return "fake_key"
        if key == "JIRA_TRACKED_PROJECTS":
            return "TESTPROJ"
        return default
    mock_settings.get.side_effect = settings_get

    # Mock ChatOpenAI
    mock_chat = mocker.patch("app.tasks.ChatOpenAI")

    # Mock JiraClient
    mock_jira_client_class = mocker.patch("app.tasks.JiraClient")
    mock_jira = MagicMock()
    mock_jira_client_class.return_value = mock_jira

    # Fake issue
    fake_issue = MagicMock()
    fake_issue.key = "TESTPROJ-123"

    mock_jira.search_issues.return_value = [fake_issue]

    # Fake comments (with marker)
    fake_comment = MagicMock()
    fake_comment.body = "Existing reminder <!-- AUTO_GENERATED_JIRA_STALE_IN_PROGRESS_REMINDER -->"
    mock_jira.get_comments.return_value = [fake_comment]

    result = await jira_stale_in_progress_reminder_task()

    assert "completed" in result
    mock_jira.add_comment.assert_not_called()
