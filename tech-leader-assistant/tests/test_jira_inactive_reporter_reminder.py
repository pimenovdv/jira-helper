import pytest
from unittest.mock import MagicMock
from app.tasks import jira_inactive_reporter_reminder_task

@pytest.mark.asyncio
async def test_jira_inactive_reporter_reminder_task_no_api_key(mocker):
    mock_settings = MagicMock(); mock_settings.get.side_effect = lambda k, d="": "" if k == "OPENAI_API_KEY" else d; mocker.patch("app.tasks.settings", mock_settings)
    result = await jira_inactive_reporter_reminder_task()
    assert result == "Jira inactive reporter reminder task skipped (no OpenAI API key)"

@pytest.mark.asyncio
async def test_jira_inactive_reporter_reminder_task_success(mocker):
    # Mock settings
    def mock_settings_get(key, default=""):
        if key == "OPENAI_API_KEY":
            return "test_key"
        if key == "JIRA_TRACKED_PROJECTS":
            return "TEST"
        return default

    mock_settings = MagicMock(); mock_settings.get.side_effect = mock_settings_get; mocker.patch("app.tasks.settings", mock_settings)

    mock_llm_instance = MagicMock()
    mock_llm_instance.ainvoke = mocker.AsyncMock(return_value=MagicMock(content="Please verify this issue."))
    mocker.patch("app.tasks.ChatOpenAI", return_value=mock_llm_instance)

    mock_jira_client_instance = MagicMock()
    mock_issue = MagicMock()
    mock_issue.key = "TEST-123"
    mock_issue.fields.reporter.displayName = "Test User"
    mock_issue.fields.reporter.accountId = "12345"
    mock_jira_client_instance.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "Some existing comment"
    mock_jira_client_instance.get_comments.return_value = [mock_comment]

    mocker.patch("app.tasks.JiraClient", return_value=mock_jira_client_instance)

    result = await jira_inactive_reporter_reminder_task()

    assert result == "Jira inactive reporter reminder task complete."
    mock_jira_client_instance.search_issues.assert_called_once_with('project = "TEST" AND status = "Resolved" AND updated <= -3d')
    mock_jira_client_instance.get_comments.assert_called_once_with("TEST-123")
    mock_jira_client_instance.add_comment.assert_called_once()
    args, _ = mock_jira_client_instance.add_comment.call_args
    assert args[0] == "TEST-123"
    assert "Please verify this issue." in args[1]
    assert "<!-- AUTO_GENERATED_JIRA_INACTIVE_REPORTER_REMINDER -->" in args[1]
    mock_llm_instance.ainvoke.assert_called_once()

@pytest.mark.asyncio
async def test_jira_inactive_reporter_reminder_task_already_notified(mocker):
    def mock_settings_get(key, default=""):
        if key == "OPENAI_API_KEY":
            return "test_key"
        if key == "JIRA_TRACKED_PROJECTS":
            return "TEST"
        return default

    mock_settings = MagicMock(); mock_settings.get.side_effect = mock_settings_get; mocker.patch("app.tasks.settings", mock_settings)

    mock_llm_instance = MagicMock()
    mock_llm_instance.ainvoke = mocker.AsyncMock()
    mocker.patch("app.tasks.ChatOpenAI", return_value=mock_llm_instance)

    mock_jira_client_instance = MagicMock()
    mock_issue = MagicMock()
    mock_issue.key = "TEST-124"
    mock_jira_client_instance.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "Existing comment\n\n<!-- AUTO_GENERATED_JIRA_INACTIVE_REPORTER_REMINDER -->"
    mock_jira_client_instance.get_comments.return_value = [mock_comment]

    mocker.patch("app.tasks.JiraClient", return_value=mock_jira_client_instance)

    result = await jira_inactive_reporter_reminder_task()

    assert result == "Jira inactive reporter reminder task complete."
    mock_jira_client_instance.search_issues.assert_called_once_with('project = "TEST" AND status = "Resolved" AND updated <= -3d')
    mock_jira_client_instance.get_comments.assert_called_once_with("TEST-124")
    mock_jira_client_instance.add_comment.assert_not_called()
    mock_llm_instance.ainvoke.assert_not_called()
