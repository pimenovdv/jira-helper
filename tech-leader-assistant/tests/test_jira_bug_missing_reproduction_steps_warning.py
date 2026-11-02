import pytest
from app.tasks import jira_bug_missing_reproduction_steps_warning_task

class MockComment:
    def __init__(self, body):
        self.body = body

class MockUser:
    def __init__(self, accountId):
        self.accountId = accountId

class MockFields:
    def __init__(self, description, assignee=None):
        self.description = description
        self.assignee = assignee

class MockIssue:
    def __init__(self, key, fields):
        self.key = key
        self.fields = fields

@pytest.fixture
def mock_settings(mocker):
    mock_set = mocker.patch("app.tasks.settings")
    mock_set.get.return_value = "PROJ1, PROJ2"
    return mock_set

@pytest.fixture
def mock_jira_client(mocker):
    return mocker.patch("app.tasks.JiraClient")

@pytest.mark.asyncio
async def test_jira_bug_missing_reproduction_steps_warning_task_adds_comment(mock_settings, mock_jira_client):
    mock_issue = MockIssue(
        key="PROJ1-1",
        fields=MockFields(
            description="The app crashes when I click the button.",
            assignee=MockUser(accountId="user123")
        )
    )

    mock_client_instance = mock_jira_client.return_value
    mock_client_instance.search_issues.return_value = [mock_issue]
    mock_client_instance.get_comments.return_value = []

    await jira_bug_missing_reproduction_steps_warning_task()

    mock_client_instance.search_issues.assert_called_once_with(
        'project IN ("PROJ1", "PROJ2") AND type = Bug AND statusCategory != Done', maxResults=100
    )
    mock_client_instance.add_comment.assert_called_once()
    args, kwargs = mock_client_instance.add_comment.call_args
    assert args[0] == "PROJ1-1"
    assert "<!-- AUTO_GENERATED_MISSING_REPRODUCTION_STEPS_WARNING -->" in args[1]
    assert "[~accountid:user123]" in args[1]
    assert "missing **steps to reproduce**" in args[1]

@pytest.mark.asyncio
async def test_jira_bug_missing_reproduction_steps_warning_task_no_comment_if_steps_exist(mock_settings, mock_jira_client):
    mock_issue = MockIssue(
        key="PROJ1-2",
        fields=MockFields(
            description="The app crashes.\nSteps to reproduce:\n1. Click button.\n2. Crash.",
            assignee=MockUser(accountId="user123")
        )
    )

    mock_client_instance = mock_jira_client.return_value
    mock_client_instance.search_issues.return_value = [mock_issue]

    await jira_bug_missing_reproduction_steps_warning_task()

    mock_client_instance.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_bug_missing_reproduction_steps_warning_task_no_comment_if_already_warned(mock_settings, mock_jira_client):
    mock_issue = MockIssue(
        key="PROJ1-3",
        fields=MockFields(
            description="The app crashes.",
            assignee=MockUser(accountId="user123")
        )
    )

    mock_client_instance = mock_jira_client.return_value
    mock_client_instance.search_issues.return_value = [mock_issue]
    mock_client_instance.get_comments.return_value = [
        MockComment(body="Some other comment"),
        MockComment(body="<!-- AUTO_GENERATED_MISSING_REPRODUCTION_STEPS_WARNING -->\nHi!")
    ]

    await jira_bug_missing_reproduction_steps_warning_task()

    mock_client_instance.add_comment.assert_not_called()
