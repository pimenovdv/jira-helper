import pytest
from app.tasks import jira_missing_description_reminder_task
from unittest.mock import MagicMock

@pytest.fixture
def mock_jira_client(mocker):
    return mocker.patch("app.tasks.JiraClient")

@pytest.fixture
def mock_chat_openai(mocker):
    return mocker.patch("app.tasks.ChatOpenAI")

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.tasks.settings")
    mock.get.side_effect = lambda key, default="": {
        "OPENAI_API_KEY": "test-key",
        "JIRA_TRACKED_PROJECTS": "PROJ1",
    }.get(key, default)
    return mock

@pytest.mark.asyncio
async def test_jira_missing_description_reminder_task_success(mock_jira_client, mock_chat_openai, mock_settings):
    # Setup Jira Client mock
    mock_instance = mock_jira_client.return_value

    # Mock Jira issue
    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    # Empty description
    mock_issue.fields.description = ""
    mock_instance.search_issues.return_value = [mock_issue]

    # Mock comments (no previous reminder)
    mock_comment = MagicMock()
    mock_comment.body = "Some comment"
    mock_instance.get_comments.return_value = [mock_comment]

    # Setup LLM mock
    mock_llm_instance = mock_chat_openai.return_value
    mock_llm_response = MagicMock()
    mock_llm_response.content = "Пожалуйста, добавьте описание."
    mock_llm_instance.invoke.return_value = mock_llm_response

    # Run the task
    result = await jira_missing_description_reminder_task()

    assert result == "Jira missing description reminder task completed"

    # Verify add_comment was called
    mock_instance.add_comment.assert_called_once()
    call_args = mock_instance.add_comment.call_args[0]
    assert call_args[0] == "PROJ1-123"
    assert "Пожалуйста, добавьте описание." in call_args[1]
    assert "<!-- AUTO_GENERATED_JIRA_MISSING_DESCRIPTION_REMINDER -->" in call_args[1]

@pytest.mark.asyncio
async def test_jira_missing_description_reminder_task_short_description(mock_jira_client, mock_chat_openai, mock_settings):
    # Setup Jira Client mock
    mock_instance = mock_jira_client.return_value

    # Mock Jira issue with short description
    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.description = "Too short" # length < 20
    mock_instance.search_issues.return_value = [mock_issue]

    # Mock comments
    mock_instance.get_comments.return_value = []

    # Setup LLM mock
    mock_llm_instance = mock_chat_openai.return_value
    mock_llm_response = MagicMock()
    mock_llm_response.content = "Пожалуйста, добавьте описание."
    mock_llm_instance.invoke.return_value = mock_llm_response

    # Run the task
    result = await jira_missing_description_reminder_task()

    assert result == "Jira missing description reminder task completed"

    # Verify add_comment was called
    mock_instance.add_comment.assert_called_once()

@pytest.mark.asyncio
async def test_jira_missing_description_reminder_task_has_description(mock_jira_client, mock_chat_openai, mock_settings):
    # Setup Jira Client mock
    mock_instance = mock_jira_client.return_value

    # Mock Jira issue with valid description
    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.description = "This is a properly long description that exceeds twenty characters."
    mock_instance.search_issues.return_value = [mock_issue]

    # Run the task
    result = await jira_missing_description_reminder_task()

    assert result == "Jira missing description reminder task completed"

    # Verify add_comment was NOT called
    mock_instance.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_missing_description_reminder_task_already_reminded(mock_jira_client, mock_chat_openai, mock_settings):
    # Setup Jira Client mock
    mock_instance = mock_jira_client.return_value

    # Mock Jira issue with empty description
    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.description = ""
    mock_instance.search_issues.return_value = [mock_issue]

    # Mock comments with previous reminder
    mock_comment = MagicMock()
    mock_comment.body = "<!-- AUTO_GENERATED_JIRA_MISSING_DESCRIPTION_REMINDER -->"
    mock_instance.get_comments.return_value = [mock_comment]

    # Run the task
    result = await jira_missing_description_reminder_task()

    assert result == "Jira missing description reminder task completed"

    # Verify add_comment was NOT called
    mock_instance.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_missing_description_reminder_task_no_openai_key(mock_jira_client, mock_chat_openai, mocker):
    # Setup settings without OPENAI_API_KEY
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = ""

    # Run the task
    result = await jira_missing_description_reminder_task()

    assert result == "Jira missing description reminder task skipped (no OpenAI API key)"
    mock_jira_client.return_value.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_missing_description_reminder_task_exception(mock_jira_client, mock_chat_openai, mock_settings):
    # Setup Jira Client mock
    mock_instance = mock_jira_client.return_value

    # Mock Jira issue
    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.description = ""
    mock_instance.search_issues.return_value = [mock_issue]

    # Trigger exception when getting comments
    mock_instance.get_comments.side_effect = Exception("API Error")

    # Run the task
    result = await jira_missing_description_reminder_task()

    assert result == "Jira missing description reminder task completed"
    mock_instance.add_comment.assert_not_called()
