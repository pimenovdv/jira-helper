import pytest
import logging
from unittest.mock import MagicMock
from app.tasks import jira_missing_priority_reminder_task
from langchain_core.messages import SystemMessage, HumanMessage

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.tasks.settings")
    mock.get.side_effect = lambda key, default="": {
        "OPENAI_API_KEY": "test_key",
        "JIRA_TRACKED_PROJECTS": "PROJ1",
    }.get(key, default)
    return mock

@pytest.fixture
def mock_jira_client_class(mocker):
    return mocker.patch("app.tasks.JiraClient")

@pytest.fixture
def mock_chat_openai(mocker):
    return mocker.patch("app.tasks.ChatOpenAI")

@pytest.mark.asyncio
async def test_missing_priority_no_api_key(mocker, mock_settings):
    mock_settings.get.side_effect = lambda key, default="": "" if key == "OPENAI_API_KEY" else "PROJ1"
    result = await jira_missing_priority_reminder_task()
    assert result == "Jira missing priority reminder task skipped (no OpenAI API key)"

@pytest.mark.asyncio
async def test_missing_priority_task_success(mocker, mock_settings, mock_jira_client_class, mock_chat_openai):
    mock_client = mock_jira_client_class.return_value

    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.priority = None

    # Simulate an issue with no previous priority reminder comment
    mock_comment = MagicMock()
    mock_comment.body = "Some other comment"
    mock_client.get_comments.return_value = [mock_comment]

    mock_client.search_issues.return_value = [mock_issue]

    mock_llm_instance = mock_chat_openai.return_value
    mock_response = MagicMock()
    mock_response.content = "Please add a priority."
    mock_llm_instance.ainvoke = mocker.AsyncMock(return_value=mock_response)

    result = await jira_missing_priority_reminder_task()

    assert result == "Jira missing priority reminder task completed"
    mock_client.search_issues.assert_called_once_with('project = "PROJ1" AND sprint in openSprints() AND statusCategory != Done')
    mock_llm_instance.ainvoke.assert_awaited_once()

    expected_message = "Please add a priority.\n\n<!-- AUTO_GENERATED_JIRA_MISSING_PRIORITY_REMINDER -->"
    mock_client.add_comment.assert_called_once_with("PROJ1-123", expected_message)

@pytest.mark.asyncio
async def test_missing_priority_task_already_reminded(mocker, mock_settings, mock_jira_client_class, mock_chat_openai):
    mock_client = mock_jira_client_class.return_value

    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.priority = None

    # Simulate an issue that already has the reminder comment
    mock_comment = MagicMock()
    mock_comment.body = "<!-- AUTO_GENERATED_JIRA_MISSING_PRIORITY_REMINDER -->\nPlease add a priority."
    mock_client.get_comments.return_value = [mock_comment]

    mock_client.search_issues.return_value = [mock_issue]

    mock_llm_instance = mock_chat_openai.return_value
    mock_llm_instance.ainvoke = mocker.AsyncMock()

    result = await jira_missing_priority_reminder_task()

    assert result == "Jira missing priority reminder task completed"
    mock_llm_instance.ainvoke.assert_not_called()
    mock_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_missing_priority_task_has_priority(mocker, mock_settings, mock_jira_client_class, mock_chat_openai):
    mock_client = mock_jira_client_class.return_value

    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.priority = "High"

    mock_client.search_issues.return_value = [mock_issue]

    mock_llm_instance = mock_chat_openai.return_value
    mock_llm_instance.ainvoke = mocker.AsyncMock()

    result = await jira_missing_priority_reminder_task()

    assert result == "Jira missing priority reminder task completed"
    mock_llm_instance.ainvoke.assert_not_called()
    mock_client.add_comment.assert_not_called()
