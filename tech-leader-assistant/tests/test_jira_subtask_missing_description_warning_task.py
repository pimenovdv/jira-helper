import pytest
from unittest.mock import MagicMock
from app.tasks import jira_subtask_missing_description_warning_task

@pytest.fixture
def mock_jira_client(mocker):
    return mocker.patch("app.clients.jira_client.JiraClient")

@pytest.fixture
def mock_settings(mocker):
    mock_set = mocker.patch("app.tasks.settings")
    mock_set.get.return_value = "TEST_PROJ"
    return mock_set

@pytest.mark.asyncio
async def test_subtask_missing_description_adds_comment(mock_jira_client, mock_settings):
    client_instance = mock_jira_client.return_value

    mock_issue = MagicMock()
    mock_issue.key = "TEST-1"
    mock_issue.fields.description = None

    client_instance.search_issues.return_value = [mock_issue]
    client_instance.get_comments.return_value = []

    result = await jira_subtask_missing_description_warning_task()

    client_instance.search_issues.assert_called_once_with('project = "TEST_PROJ" AND issuetype = "Sub-task" AND statusCategory != Done')
    client_instance.add_comment.assert_called_once()
    args, _ = client_instance.add_comment.call_args
    assert args[0] == "TEST-1"
    assert "AUTO_GENERATED_SUBTASK_MISSING_DESCRIPTION_WARNING" in args[1]
    assert "warned 1 subtasks" in result.lower()

@pytest.mark.asyncio
async def test_subtask_with_description_no_comment(mock_jira_client, mock_settings):
    client_instance = mock_jira_client.return_value

    mock_issue = MagicMock()
    mock_issue.key = "TEST-2"
    mock_issue.fields.description = "This is a valid description."

    client_instance.search_issues.return_value = [mock_issue]

    result = await jira_subtask_missing_description_warning_task()

    client_instance.add_comment.assert_not_called()
    assert "warned 0 subtasks" in result.lower()

@pytest.mark.asyncio
async def test_subtask_missing_description_already_warned(mock_jira_client, mock_settings):
    client_instance = mock_jira_client.return_value

    mock_issue = MagicMock()
    mock_issue.key = "TEST-3"
    mock_issue.fields.description = "   "

    mock_comment = MagicMock()
    mock_comment.body = "<!-- AUTO_GENERATED_SUBTASK_MISSING_DESCRIPTION_WARNING -->\nWarning!"

    client_instance.search_issues.return_value = [mock_issue]
    client_instance.get_comments.return_value = [mock_comment]

    result = await jira_subtask_missing_description_warning_task()

    client_instance.add_comment.assert_not_called()
    assert "warned 0 subtasks" in result.lower()

@pytest.mark.asyncio
async def test_subtask_exception_handling(mock_jira_client, mock_settings):
    client_instance = mock_jira_client.return_value
    client_instance.search_issues.side_effect = Exception("API Error")

    result = await jira_subtask_missing_description_warning_task()

    assert "warned 0 subtasks" in result.lower()
