import pytest
import logging
from unittest.mock import MagicMock
from app.tasks import jira_missing_component_reminder_task
from app.clients import settings

@pytest.fixture
def mock_openai(mocker):
    mock_chat = mocker.MagicMock()
    mock_response = mocker.MagicMock()
    mock_response.content = "Please assign a component."
    mock_chat.invoke.return_value = mock_response
    mocker.patch("app.tasks.ChatOpenAI", return_value=mock_chat)
    return mock_chat

@pytest.fixture
def mock_jira_client(mocker):
    mock_client = mocker.MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=mock_client)
    return mock_client

@pytest.fixture(autouse=True)
def setup_settings():
    original_key = settings.get("OPENAI_API_KEY")
    original_projects = settings.get("JIRA_TRACKED_PROJECTS")

    settings.set("OPENAI_API_KEY", "test-key")
    settings.set("JIRA_TRACKED_PROJECTS", "TLA")

    yield

    settings.set("OPENAI_API_KEY", original_key)
    settings.set("JIRA_TRACKED_PROJECTS", original_projects)

@pytest.mark.asyncio
async def test_jira_missing_component_reminder_task_success(mock_jira_client, mock_openai, mocker):
    mock_issue = mocker.MagicMock()
    mock_issue.key = "TLA-123"
    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_jira_client.get_comments.return_value = []

    result = await jira_missing_component_reminder_task()

    assert result == "Jira missing component reminder task completed"
    mock_jira_client.search_issues.assert_called_once_with('project = "TLA" AND sprint in openSprints() AND components IS EMPTY AND statusCategory != Done')
    mock_jira_client.add_comment.assert_called_once()
    assert "Please assign a component." in mock_jira_client.add_comment.call_args[0][1]
    assert "<!-- AUTO_GENERATED_JIRA_MISSING_COMPONENT_REMINDER -->" in mock_jira_client.add_comment.call_args[0][1]

@pytest.mark.asyncio
async def test_jira_missing_component_reminder_task_no_api_key(caplog):
    settings.set("OPENAI_API_KEY", "")
    with caplog.at_level(logging.WARNING):
        result = await jira_missing_component_reminder_task()

    assert result == "Jira missing component reminder task skipped (no OpenAI API key)"
    assert "OPENAI_API_KEY not found" in caplog.text

@pytest.mark.asyncio
async def test_jira_missing_component_reminder_task_already_reminded(mock_jira_client, mock_openai, mocker):
    mock_issue = mocker.MagicMock()
    mock_issue.key = "TLA-123"
    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_comment = mocker.MagicMock()
    mock_comment.body = "Some text <!-- AUTO_GENERATED_JIRA_MISSING_COMPONENT_REMINDER -->"
    mock_jira_client.get_comments.return_value = [mock_comment]

    result = await jira_missing_component_reminder_task()

    assert result == "Jira missing component reminder task completed"
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_missing_component_reminder_task_error(mock_jira_client, mock_openai, mocker, caplog):
    mock_issue = mocker.MagicMock()
    mock_issue.key = "TLA-123"
    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_jira_client.get_comments.side_effect = Exception("Jira API error")

    with caplog.at_level(logging.ERROR):
        result = await jira_missing_component_reminder_task()

    assert result == "Jira missing component reminder task completed"
    assert "Error processing missing component reminder for issue TLA-123: Jira API error" in caplog.text
