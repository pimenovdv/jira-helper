import pytest
from unittest.mock import MagicMock
from app.tasks import jira_missing_estimation_reminder_task
from app.clients import settings
import logging

@pytest.fixture
def mock_settings(mocker):
    original_api = settings.get("OPENAI_API_KEY", None)
    original_projects = settings.get("JIRA_TRACKED_PROJECTS", None)

    settings.set("OPENAI_API_KEY", "fake_key")
    settings.set("JIRA_TRACKED_PROJECTS", "TESTPROJ")
    yield settings

    if original_api is not None:
        settings.set("OPENAI_API_KEY", original_api)
    else:
        settings.set("OPENAI_API_KEY", "")

    if original_projects is not None:
        settings.set("JIRA_TRACKED_PROJECTS", original_projects)
    else:
        settings.set("JIRA_TRACKED_PROJECTS", "")

@pytest.fixture
def mock_jira_client(mocker):
    mock_class = mocker.patch("app.tasks.JiraClient", autospec=True)
    instance = mock_class.return_value
    return instance

@pytest.fixture
def mock_llm(mocker):
    mock_llm_class = mocker.patch("app.tasks.ChatOpenAI", autospec=True)
    instance = mock_llm_class.return_value
    mock_response = MagicMock()
    mock_response.content = "Пожалуйста, добавьте оценку в задачу."
    instance.invoke.return_value = mock_response
    return instance

@pytest.mark.asyncio
async def test_missing_estimation_reminder_success(mock_settings, mock_jira_client, mock_llm):
    issue_missing = MagicMock()
    issue_missing.key = "TESTPROJ-1"
    issue_missing.fields.summary = "Task with missing estimation"
    # Both estimation fields are None
    issue_missing.fields.customfield_10016 = None
    issue_missing.fields.timeoriginalestimate = None

    issue_with_sp = MagicMock()
    issue_with_sp.key = "TESTPROJ-2"
    issue_with_sp.fields.customfield_10016 = 5.0
    issue_with_sp.fields.timeoriginalestimate = None

    issue_with_time = MagicMock()
    issue_with_time.key = "TESTPROJ-3"
    issue_with_time.fields.customfield_10016 = None
    issue_with_time.fields.timeoriginalestimate = 3600

    mock_jira_client.search_issues.return_value = [issue_missing, issue_with_sp, issue_with_time]
    mock_jira_client.get_comments.return_value = []

    result = await jira_missing_estimation_reminder_task()

    assert result == "Jira missing estimation reminder task completed"
    mock_jira_client.search_issues.assert_called_with('project = "TESTPROJ" AND sprint in openSprints()')

    # Only called for the issue missing estimation
    mock_jira_client.get_comments.assert_called_once_with("TESTPROJ-1")
    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "TESTPROJ-1"
    assert "<!-- AUTO_GENERATED_JIRA_MISSING_ESTIMATION_REMINDER -->" in args[1]
    assert "Пожалуйста, добавьте оценку в задачу." in args[1]

@pytest.mark.asyncio
async def test_missing_estimation_reminder_already_reminded(mock_settings, mock_jira_client, mock_llm):
    issue_missing = MagicMock()
    issue_missing.key = "TESTPROJ-4"
    issue_missing.fields.summary = "Task with missing estimation"
    issue_missing.fields.customfield_10016 = None
    issue_missing.fields.timeoriginalestimate = None

    mock_jira_client.search_issues.return_value = [issue_missing]

    comment = MagicMock()
    comment.body = "Some text <!-- AUTO_GENERATED_JIRA_MISSING_ESTIMATION_REMINDER -->"
    mock_jira_client.get_comments.return_value = [comment]

    result = await jira_missing_estimation_reminder_task()

    assert result == "Jira missing estimation reminder task completed"
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_missing_estimation_reminder_no_api_key(mocker, mock_jira_client):
    original_api = settings.get("OPENAI_API_KEY", None)
    settings.set("OPENAI_API_KEY", "")

    result = await jira_missing_estimation_reminder_task()

    assert result == "Jira missing estimation reminder task skipped (no OpenAI API key)"
    mock_jira_client.search_issues.assert_not_called()

    if original_api is not None:
        settings.set("OPENAI_API_KEY", original_api)

@pytest.mark.asyncio
async def test_missing_estimation_reminder_exception(mock_settings, mock_jira_client, mock_llm, caplog):
    mock_jira_client.search_issues.side_effect = Exception("Jira API error")

    with caplog.at_level(logging.ERROR):
        result = await jira_missing_estimation_reminder_task()

    assert result == "Jira missing estimation reminder task completed"
    assert "Error fetching issues for project TESTPROJ: Jira API error" in caplog.text
