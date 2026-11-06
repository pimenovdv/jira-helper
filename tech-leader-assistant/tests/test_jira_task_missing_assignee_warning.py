import pytest
from app.tasks import jira_task_missing_assignee_warning_task

class MockComment:
    def __init__(self, body):
        self.body = body

class MockUser:
    def __init__(self, accountId):
        self.accountId = accountId

class MockFields:
    def __init__(self, assignee=None):
        self.assignee = assignee

class MockIssue:
    def __init__(self, key, fields):
        self.key = key
        self.fields = fields

@pytest.fixture
def mock_settings(mocker):
    # Patch settings in app.clients since the function does `from app.clients import settings`
    mock_set = mocker.patch("app.clients.settings")
    mock_set.get.return_value = "PROJ1, PROJ2"
    return mock_set

@pytest.fixture
def mock_jira_client(mocker):
    # Patch the class in app.clients.jira_client since the function instantiates it with JiraClient()
    return mocker.patch("app.clients.jira_client.JiraClient")

@pytest.mark.asyncio
async def test_jira_task_missing_assignee_warning_missing(mock_jira_client, mock_settings):
    issue1 = MockIssue("PROJ1-1", MockFields(assignee=None))
    mock_client_instance = mock_jira_client.return_value
    mock_client_instance.search_issues.return_value = [issue1]
    mock_client_instance.get_comments.return_value = []

    res = await jira_task_missing_assignee_warning_task()

    assert "Warned 2 tasks" in res  # It should find 1 task per project, total 2
    assert mock_client_instance.add_comment.call_count == 2
    args_list = mock_client_instance.add_comment.call_args_list
    assert args_list[0][0][0] == "PROJ1-1"
    assert "missing an assignee" in args_list[0][0][1]

@pytest.mark.asyncio
async def test_jira_task_missing_assignee_warning_present(mock_jira_client, mock_settings):
    issue1 = MockIssue("PROJ1-1", MockFields(assignee=MockUser("acc-123")))
    mock_client_instance = mock_jira_client.return_value
    mock_client_instance.search_issues.return_value = [issue1]

    res = await jira_task_missing_assignee_warning_task()

    assert "Warned 0 tasks" in res
    assert mock_client_instance.add_comment.call_count == 0

@pytest.mark.asyncio
async def test_jira_task_missing_assignee_warning_already_warned(mock_jira_client, mock_settings):
    issue1 = MockIssue("PROJ1-1", MockFields(assignee=None))
    mock_client_instance = mock_jira_client.return_value
    mock_client_instance.search_issues.return_value = [issue1]
    mock_client_instance.get_comments.return_value = [MockComment("<!-- AUTO_GENERATED_TASK_MISSING_ASSIGNEE_WARNING -->")]

    res = await jira_task_missing_assignee_warning_task()

    assert "Warned 0 tasks" in res
    assert mock_client_instance.add_comment.call_count == 0

@pytest.mark.asyncio
async def test_jira_task_missing_assignee_warning_exception(mock_jira_client, mock_settings):
    mock_client_instance = mock_jira_client.return_value
    mock_client_instance.search_issues.side_effect = Exception("JIRA API Error")

    # Should not raise exception
    res = await jira_task_missing_assignee_warning_task()

    assert "Warned 0 tasks" in res
