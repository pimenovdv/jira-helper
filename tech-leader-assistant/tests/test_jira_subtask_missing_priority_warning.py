import pytest
from unittest.mock import MagicMock
from app.tasks import jira_subtask_missing_priority_warning_task

class MockIssueFields:
    def __init__(self, priority=None):
        self.priority = priority
        # Explicitly set other common attributes to avoid AttributeError
        self.assignee = None

class MockIssue:
    def __init__(self, key, priority=None):
        self.key = key
        self.fields = MockIssueFields(priority=priority)

class MockComment:
    def __init__(self, body):
        self.body = body

@pytest.fixture(autouse=True)
def mock_jira(mocker):
    # Mock the actual JIRA client instantiation
    mocker.patch('app.clients.jira_client.JIRA')

@pytest.mark.asyncio
async def test_jira_subtask_missing_priority_warning_task_warns(mocker):
    # Mock settings
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = "PROJ1"

    # Mock JiraClient
    mock_jira_client_class = mocker.patch("app.tasks.JiraClient", autospec=True)
    mocker.patch("app.clients.jira_client.JiraClient", mock_jira_client_class)
    mock_jira_instance = mock_jira_client_class.return_value

    # Setup issue missing priority
    mock_issue = MockIssue("PROJ1-1", priority=None)
    mock_jira_instance.search_issues.return_value = [mock_issue]

    # Setup comments (no previous warning)
    mock_jira_instance.get_comments.return_value = []

    result = await jira_subtask_missing_priority_warning_task()

    assert "Warned 1 subtasks" in result
    mock_jira_instance.search_issues.assert_called_once_with('project = "PROJ1" AND issuetype = "Sub-task" AND statusCategory != Done')
    mock_jira_instance.get_comments.assert_called_once_with("PROJ1-1")
    mock_jira_instance.add_comment.assert_called_once()
    call_args = mock_jira_instance.add_comment.call_args[0]
    assert call_args[0] == "PROJ1-1"
    assert "missing a priority" in call_args[1]
    assert "AUTO_GENERATED_JIRA_SUBTASK_MISSING_PRIORITY_WARNING" in call_args[1]

@pytest.mark.asyncio
async def test_jira_subtask_missing_priority_warning_task_has_priority(mocker):
    # Mock settings
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = "PROJ1"

    # Mock JiraClient
    mock_jira_client_class = mocker.patch("app.tasks.JiraClient")
    mocker.patch("app.clients.jira_client.JiraClient", mock_jira_client_class)
    mock_jira_instance = mock_jira_client_class.return_value

    # Setup issue with priority
    mock_issue = MockIssue("PROJ1-2", priority="High")
    mock_jira_instance.search_issues.return_value = [mock_issue]

    result = await jira_subtask_missing_priority_warning_task()

    assert "Warned 0 subtasks" in result
    mock_jira_instance.search_issues.assert_called_once()
    mock_jira_instance.get_comments.assert_not_called()
    mock_jira_instance.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_subtask_missing_priority_warning_task_already_warned(mocker):
    # Mock settings
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = "PROJ1"

    # Mock JiraClient
    mock_jira_client_class = mocker.patch("app.tasks.JiraClient")
    mocker.patch("app.clients.jira_client.JiraClient", mock_jira_client_class)
    mock_jira_instance = mock_jira_client_class.return_value

    # Setup issue missing priority
    mock_issue = MockIssue("PROJ1-3", priority=None)
    mock_jira_instance.search_issues.return_value = [mock_issue]

    # Setup comments (already has warning)
    mock_jira_instance.get_comments.return_value = [
        MockComment("Some comment"),
        MockComment("<!-- AUTO_GENERATED_JIRA_SUBTASK_MISSING_PRIORITY_WARNING -->")
    ]

    result = await jira_subtask_missing_priority_warning_task()

    assert "Warned 0 subtasks" in result
    mock_jira_instance.search_issues.assert_called_once()
    mock_jira_instance.get_comments.assert_called_once_with("PROJ1-3")
    mock_jira_instance.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_subtask_missing_priority_warning_task_handles_exception(mocker):
    # Mock settings
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = "PROJ1"

    # Mock JiraClient to raise exception on search
    mock_jira_client_class = mocker.patch("app.tasks.JiraClient", autospec=True)
    mocker.patch("app.clients.jira_client.JiraClient", mock_jira_client_class)
    mock_jira_instance = mock_jira_client_class.return_value
    mock_jira_instance.search_issues.side_effect = Exception("API Error")

    result = await jira_subtask_missing_priority_warning_task()

    assert "Warned 0 subtasks" in result
    mock_jira_instance.search_issues.assert_called_once()
