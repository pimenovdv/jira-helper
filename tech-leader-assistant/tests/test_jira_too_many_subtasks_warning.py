
import pytest
from unittest.mock import MagicMock
from app.tasks import jira_too_many_subtasks_warning_task

@pytest.fixture(autouse=True)
def mock_jira_constructor(mocker):
    # Prevent JiraClient from actually connecting during test setup
    mocker.patch("app.clients.jira_client.JIRA")

@pytest.mark.asyncio
async def test_jira_too_many_subtasks_warning_task_no_issues(mocker):
    mock_jira_client = mocker.patch("app.clients.jira_client.JiraClient")
    mock_instance = mock_jira_client.return_value
    mock_instance.search_issues.return_value = []

    await jira_too_many_subtasks_warning_task()

    mock_instance.search_issues.assert_called_once_with("resolution = Unresolved AND issuetype not in (Epic, Sub-task)")
    mock_instance.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_too_many_subtasks_warning_task_few_subtasks(mocker):
    mock_jira_client = mocker.patch("app.clients.jira_client.JiraClient")
    mock_instance = mock_jira_client.return_value

    issue_few = MagicMock()
    issue_few.key = "PROJ-1"
    issue_few.fields.subtasks = [1, 2, 3] # 3 subtasks
    mock_instance.search_issues.return_value = [issue_few]

    await jira_too_many_subtasks_warning_task()

    mock_instance.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_too_many_subtasks_warning_task_many_subtasks_no_comment(mocker):
    mock_jira_client = mocker.patch("app.clients.jira_client.JiraClient")
    mock_instance = mock_jira_client.return_value

    issue_many = MagicMock()
    issue_many.key = "PROJ-2"
    issue_many.fields.subtasks = [1] * 10 # 10 subtasks
    issue_many.fields.assignee.displayName = "John Doe"
    mock_instance.search_issues.return_value = [issue_many]

    # No comments currently
    mock_instance.get_comments.return_value = []

    await jira_too_many_subtasks_warning_task()

    mock_instance.add_comment.assert_called_once()
    args, kwargs = mock_instance.add_comment.call_args
    assert args[0] == "PROJ-2"
    assert "Hi John Doe" in args[1]
    assert "<!-- AUTO_GENERATED_TOO_MANY_SUBTASKS_WARNING -->" in args[1]

@pytest.mark.asyncio
async def test_jira_too_many_subtasks_warning_task_many_subtasks_already_commented(mocker):
    mock_jira_client = mocker.patch("app.clients.jira_client.JiraClient")
    mock_instance = mock_jira_client.return_value

    issue_many = MagicMock()
    issue_many.key = "PROJ-3"
    issue_many.fields.subtasks = [1] * 11
    mock_instance.search_issues.return_value = [issue_many]

    # Comment already exists
    comment = MagicMock()
    comment.body = "Some text <!-- AUTO_GENERATED_TOO_MANY_SUBTASKS_WARNING --> some more text"
    mock_instance.get_comments.return_value = [comment]

    await jira_too_many_subtasks_warning_task()

    mock_instance.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_too_many_subtasks_warning_task_many_subtasks_no_assignee(mocker):
    mock_jira_client = mocker.patch("app.clients.jira_client.JiraClient")
    mock_instance = mock_jira_client.return_value

    issue_many = MagicMock()
    issue_many.key = "PROJ-4"
    issue_many.fields.subtasks = [1] * 10
    del issue_many.fields.assignee
    mock_instance.search_issues.return_value = [issue_many]
    mock_instance.get_comments.return_value = []

    await jira_too_many_subtasks_warning_task()

    mock_instance.add_comment.assert_called_once()
    args, kwargs = mock_instance.add_comment.call_args
    assert "Hi Creator" in args[1]
