import pytest
from app.tasks import jira_epic_missing_assignee_warning_task

class MockIssue:
    def __init__(self, key, assignee):
        self.key = key
        class Fields:
            pass
        self.fields = Fields()
        if assignee is not None:
            self.fields.assignee = assignee

class MockComment:
    def __init__(self, body):
        self.body = body

@pytest.fixture
def mock_jira_client(mocker):
    return mocker.patch("app.clients.jira_client.JiraClient")

@pytest.fixture
def mock_settings(mocker):
    mock_set = mocker.patch("app.clients.settings")
    mock_set.get.return_value = "PROJ1"
    return mock_set

@pytest.mark.asyncio
async def test_jira_epic_missing_assignee_warning_task_with_assignee(mock_jira_client, mock_settings):
    mock_instance = mock_jira_client.return_value
    mock_instance.search_issues.return_value = [
        MockIssue("PROJ1-1", "user1")
    ]

    result = await jira_epic_missing_assignee_warning_task()

    assert result == "Jira epic missing assignee warning task completed. Warned 0 epics."
    mock_instance.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_epic_missing_assignee_warning_task_without_assignee_no_comment(mock_jira_client, mock_settings):
    mock_instance = mock_jira_client.return_value
    mock_instance.search_issues.return_value = [
        MockIssue("PROJ1-2", None)
    ]
    mock_instance.get_comments.return_value = [MockComment("Some comment")]

    result = await jira_epic_missing_assignee_warning_task()

    assert result == "Jira epic missing assignee warning task completed. Warned 1 epics."
    mock_instance.add_comment.assert_called_once()
    args, _ = mock_instance.add_comment.call_args
    assert args[0] == "PROJ1-2"
    assert "⚠️ **Warning**: This Epic is missing an assignee." in args[1]
    assert "<!-- AUTO_GENERATED_EPIC_MISSING_ASSIGNEE_WARNING -->" in args[1]

@pytest.mark.asyncio
async def test_jira_epic_missing_assignee_warning_task_without_assignee_with_comment(mock_jira_client, mock_settings):
    mock_instance = mock_jira_client.return_value
    mock_instance.search_issues.return_value = [
        MockIssue("PROJ1-3", None)
    ]
    mock_instance.get_comments.return_value = [MockComment("Some comment <!-- AUTO_GENERATED_EPIC_MISSING_ASSIGNEE_WARNING -->")]

    result = await jira_epic_missing_assignee_warning_task()

    assert result == "Jira epic missing assignee warning task completed. Warned 0 epics."
    mock_instance.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_epic_missing_assignee_warning_task_exception_handling(mock_jira_client, mock_settings):
    mock_instance = mock_jira_client.return_value
    mock_instance.search_issues.side_effect = Exception("Test Error")

    result = await jira_epic_missing_assignee_warning_task()

    assert result == "Jira epic missing assignee warning task completed. Warned 0 epics."
