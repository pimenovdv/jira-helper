import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
from app.tasks import stale_jira_task_reminder_task
from app.clients import settings

@pytest.fixture
def mock_settings(mocker):
    # Instead of patching settings.get directly which doesn't seem to intercept cleanly
    # when called from inside tasks.py, we mutate the instance for the test.
    original_api = settings.get("OPENAI_API_KEY", None)
    original_projects = settings.get("JIRA_TRACKED_PROJECTS", None)

    settings.set("OPENAI_API_KEY", "fake_key")
    settings.set("JIRA_TRACKED_PROJECTS", "TESTPROJ")
    yield settings

    # Restore
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
    # Create mock class
    mock_class = mocker.patch("app.tasks.JiraClient", autospec=True)
    instance = mock_class.return_value
    return instance

@pytest.fixture
def mock_llm(mocker):
    # Mock ChatOpenAI
    mock_llm_class = mocker.patch("app.tasks.ChatOpenAI", autospec=True)
    instance = mock_llm_class.return_value
    mock_response = MagicMock()
    mock_response.content = "Напоминание о задаче!"
    instance.invoke.return_value = mock_response
    return instance

@pytest.mark.asyncio
async def test_stale_jira_task_reminder_task_success(mock_settings, mock_jira_client, mock_llm):
    now = datetime.now(timezone.utc)
    stale_date = (now - timedelta(days=10)).isoformat()
    recent_date = (now - timedelta(days=2)).isoformat()

    # Create mock issues
    stale_issue = MagicMock()
    stale_issue.key = "TESTPROJ-1"
    stale_issue.fields.updated = stale_date
    stale_issue.fields.summary = "Stale Task"

    recent_issue = MagicMock()
    recent_issue.key = "TESTPROJ-2"
    recent_issue.fields.updated = recent_date
    recent_issue.fields.summary = "Recent Task"

    mock_jira_client.search_issues.return_value = [stale_issue, recent_issue]

    # Mock comments: issue 1 has no reminder, issue 2 has none
    mock_jira_client.get_comments.return_value = []

    result = await stale_jira_task_reminder_task()

    assert result == "Stale Jira task reminder task completed"
    mock_jira_client.search_issues.assert_called_with('project = "TESTPROJ" AND statusCategory IN ("In Progress") AND updated <= -7d')
    mock_jira_client.get_comments.assert_called_once_with("TESTPROJ-1")
    mock_jira_client.add_comment.assert_called_once()
    args, kwargs = mock_jira_client.add_comment.call_args
    assert args[0] == "TESTPROJ-1"
    assert "<!-- AUTO_GENERATED_STALE_JIRA_TASK_REMINDER -->" in args[1]
    assert "Напоминание о задаче!" in args[1]

@pytest.mark.asyncio
async def test_stale_jira_task_reminder_already_reminded(mock_settings, mock_jira_client, mock_llm):
    now = datetime.now(timezone.utc)
    stale_date = (now - timedelta(days=10)).isoformat()

    stale_issue = MagicMock()
    stale_issue.key = "TESTPROJ-3"
    stale_issue.fields.updated = stale_date
    stale_issue.fields.summary = "Already Reminded Task"

    mock_jira_client.search_issues.return_value = [stale_issue]

    comment = MagicMock()
    comment.body = "<!-- AUTO_GENERATED_STALE_JIRA_TASK_REMINDER -->\nНапоминание о задаче!"
    mock_jira_client.get_comments.return_value = [comment]

    result = await stale_jira_task_reminder_task()

    assert result == "Stale Jira task reminder task completed"
    mock_jira_client.search_issues.assert_called_with('project = "TESTPROJ" AND statusCategory IN ("In Progress") AND updated <= -7d')
    mock_jira_client.get_comments.assert_called_once_with("TESTPROJ-3")
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_stale_jira_task_reminder_no_api_key(mocker, mock_jira_client):
    original_api = settings.get("OPENAI_API_KEY", None)
    settings.set("OPENAI_API_KEY", "")

    result = await stale_jira_task_reminder_task()
    assert result == "Stale Jira task reminder task skipped (no OpenAI API key)"

    # Restore
    if original_api is not None:
        settings.set("OPENAI_API_KEY", original_api)
