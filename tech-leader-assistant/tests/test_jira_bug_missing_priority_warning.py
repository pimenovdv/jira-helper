import pytest
from unittest.mock import MagicMock, call
from app.tasks import jira_bug_missing_priority_warning_task

@pytest.fixture(autouse=True)
def mock_jira_class(mocker):
    # Mock JIRA client initialization to avoid actual connection attempts
    mocker.patch('app.clients.jira_client.JIRA')

@pytest.mark.asyncio
async def test_jira_bug_missing_priority_warning_task_no_projects(mocker):
    # Setup mock settings to return no projects
    mock_settings = mocker.patch("app.clients.settings")
    mock_settings.get.return_value = ""

    # Run the task
    result = await jira_bug_missing_priority_warning_task()

    # Assertions
    assert "Jira bug missing priority warning task completed. Warned 0 bugs." in result
    mock_settings.get.assert_called_once_with("JIRA_TRACKED_PROJECTS", "")


@pytest.mark.asyncio
async def test_jira_bug_missing_priority_warning_task_with_priority(mocker):
    # Setup mock settings
    mock_settings = mocker.patch("app.clients.settings")
    mock_settings.get.return_value = "PROJ"

    # Mock JiraClient
    mock_jira_client_class = mocker.patch("app.clients.jira_client.JiraClient")
    mock_jira_client_instance = mock_jira_client_class.return_value

    # Create a mock issue with a priority
    mock_issue = MagicMock()
    mock_issue.key = "PROJ-1"
    mock_issue.fields.priority = MagicMock()
    mock_issue.fields.priority.name = "High"

    mock_jira_client_instance.search_issues.return_value = [mock_issue]

    # Run the task
    result = await jira_bug_missing_priority_warning_task()

    # Assertions
    mock_jira_client_instance.search_issues.assert_called_once_with('project = "PROJ" AND issuetype = "Bug" AND statusCategory != Done')
    mock_jira_client_instance.get_comments.assert_not_called()
    mock_jira_client_instance.add_comment.assert_not_called()
    assert "Warned 0 bugs" in result


@pytest.mark.asyncio
async def test_jira_bug_missing_priority_warning_task_missing_priority_warns(mocker):
    # Setup mock settings
    mock_settings = mocker.patch("app.clients.settings")
    mock_settings.get.return_value = "PROJ"

    # Mock JiraClient
    mock_jira_client_class = mocker.patch("app.clients.jira_client.JiraClient")
    mock_jira_client_instance = mock_jira_client_class.return_value

    # Create a mock issue without priority
    mock_issue = MagicMock()
    mock_issue.key = "PROJ-2"
    mock_issue.fields.priority = None

    mock_jira_client_instance.search_issues.return_value = [mock_issue]

    # Mock no existing warning comments
    mock_jira_client_instance.get_comments.return_value = []

    # Run the task
    result = await jira_bug_missing_priority_warning_task()

    # Assertions
    mock_jira_client_instance.get_comments.assert_called_once_with("PROJ-2")
    mock_jira_client_instance.add_comment.assert_called_once()
    args, _ = mock_jira_client_instance.add_comment.call_args
    assert args[0] == "PROJ-2"
    assert "<!-- AUTO_GENERATED_JIRA_BUG_MISSING_PRIORITY_WARNING -->" in args[1]
    assert "Warned 1 bugs" in result


@pytest.mark.asyncio
async def test_jira_bug_missing_priority_warning_task_already_warned(mocker):
    # Setup mock settings
    mock_settings = mocker.patch("app.clients.settings")
    mock_settings.get.return_value = "PROJ"

    # Mock JiraClient
    mock_jira_client_class = mocker.patch("app.clients.jira_client.JiraClient")
    mock_jira_client_instance = mock_jira_client_class.return_value

    # Create a mock issue without priority
    mock_issue = MagicMock()
    mock_issue.key = "PROJ-3"
    mock_issue.fields.priority = None

    mock_jira_client_instance.search_issues.return_value = [mock_issue]

    # Mock existing warning comment
    mock_comment = MagicMock()
    mock_comment.body = "<!-- AUTO_GENERATED_JIRA_BUG_MISSING_PRIORITY_WARNING -->\\nWarning!"
    mock_jira_client_instance.get_comments.return_value = [mock_comment]

    # Run the task
    result = await jira_bug_missing_priority_warning_task()

    # Assertions
    mock_jira_client_instance.get_comments.assert_called_once_with("PROJ-3")
    mock_jira_client_instance.add_comment.assert_not_called()
    assert "Warned 0 bugs" in result


@pytest.mark.asyncio
async def test_jira_bug_missing_priority_warning_task_exception_handling(mocker):
    # Setup mock settings
    mock_settings = mocker.patch("app.clients.settings")
    mock_settings.get.return_value = "PROJ1, PROJ2"

    # Mock JiraClient
    mock_jira_client_class = mocker.patch("app.clients.jira_client.JiraClient")
    mock_jira_client_instance = mock_jira_client_class.return_value

    # Cause an exception on the first project, but succeed on the second
    mock_issue = MagicMock()
    mock_issue.key = "PROJ2-1"
    mock_issue.fields.priority = None

    mock_jira_client_instance.search_issues.side_effect = [Exception("API Error"), [mock_issue]]
    mock_jira_client_instance.get_comments.return_value = []

    # Run the task
    result = await jira_bug_missing_priority_warning_task()

    # Assertions
    assert mock_jira_client_instance.search_issues.call_count == 2
    mock_jira_client_instance.add_comment.assert_called_once_with(
        "PROJ2-1", mocker.ANY
    )
    assert "Warned 1 bugs" in result
