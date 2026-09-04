import pytest
from unittest.mock import MagicMock
from langchain_core.messages import SystemMessage, HumanMessage
from app.tasks import jira_missing_due_date_reminder_task

@pytest.fixture
def mock_jira_client(mocker):
    client = MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=client)
    return client

@pytest.fixture
def mock_llm(mocker):
    llm = MagicMock()
    mocker.patch("app.tasks.ChatOpenAI", return_value=llm)
    return llm

@pytest.fixture
def mock_settings(mocker):
    settings = MagicMock()
    settings.get.side_effect = lambda key, default="": {
        "OPENAI_API_KEY": "test-key",
        "JIRA_TRACKED_PROJECTS": "TEST"
    }.get(key, default)
    mocker.patch("app.tasks.settings", settings)
    return settings

@pytest.mark.asyncio
async def test_jira_missing_due_date_reminder_success(mock_settings, mock_jira_client, mock_llm, mocker):
    mock_issue = MagicMock()
    mock_issue.key = "TEST-1"
    mock_issue.fields.duedate = None
    mock_issue.fields.assignee = MagicMock(accountId="12345")
    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_jira_client.get_comments.return_value = []

    mock_response = MagicMock()
    mock_response.content = "Please add a due date."
    mock_llm.ainvoke = mocker.AsyncMock(return_value=mock_response)

    result = await jira_missing_due_date_reminder_task()

    assert result == "Jira missing due date reminder task completed."
    mock_jira_client.search_issues.assert_called_once_with('project = "TEST" AND issuetype = Epic AND statusCategory = "In Progress"')
    mock_jira_client.add_comment.assert_called_once_with("TEST-1", "Please add a due date.\n\n<!-- AUTO_GENERATED_JIRA_MISSING_DUE_DATE_REMINDER -->")

@pytest.mark.asyncio
async def test_jira_missing_due_date_reminder_skip_has_duedate(mock_settings, mock_jira_client, mock_llm, mocker):
    mock_issue = MagicMock()
    mock_issue.key = "TEST-2"
    mock_issue.fields.duedate = "2023-12-31"
    mock_jira_client.search_issues.return_value = [mock_issue]

    result = await jira_missing_due_date_reminder_task()

    assert result == "Jira missing due date reminder task completed."
    mock_jira_client.get_comments.assert_not_called()
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_missing_due_date_reminder_skip_already_reminded(mock_settings, mock_jira_client, mock_llm, mocker):
    mock_issue = MagicMock()
    mock_issue.key = "TEST-3"
    mock_issue.fields.duedate = None
    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "Please add a due date.\n\n<!-- AUTO_GENERATED_JIRA_MISSING_DUE_DATE_REMINDER -->"
    mock_jira_client.get_comments.return_value = [mock_comment]

    result = await jira_missing_due_date_reminder_task()

    assert result == "Jira missing due date reminder task completed."
    mock_jira_client.get_comments.assert_called_once_with("TEST-3")
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_missing_due_date_reminder_no_api_key(mocker):
    settings = MagicMock()
    settings.get.return_value = ""
    mocker.patch("app.tasks.settings", settings)

    result = await jira_missing_due_date_reminder_task()

    assert result == "Jira missing due date reminder task skipped (no OpenAI API key)"
