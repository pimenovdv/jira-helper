import pytest
from app.tasks import jira_story_missing_assignee_warning_task

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
    mock = mocker.patch("app.tasks.JiraClient")
    return mock.return_value

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.tasks.settings")
    mock.get.side_effect = lambda k, d="": "PROJ1" if k == "JIRA_TRACKED_PROJECTS" else d
    return mock

@pytest.mark.asyncio
async def test_jira_story_missing_assignee_warning_missing(mock_jira_client, mock_settings):
    story = MockIssue("PROJ1-1", assignee=None)
    mock_jira_client.get_issues.return_value = [story]
    mock_jira_client.get_comments.return_value = []

    result = await jira_story_missing_assignee_warning_task()

    mock_jira_client.add_comment.assert_called_once()
    assert "<!-- AUTO_GENERATED_JIRA_STORY_MISSING_ASSIGNEE_WARNING -->" in mock_jira_client.add_comment.call_args[0][1]
    assert result == "Jira story missing assignee warning task completed"

@pytest.mark.asyncio
async def test_jira_story_missing_assignee_warning_present(mock_jira_client, mock_settings):
    story = MockIssue("PROJ1-1", assignee={"name": "user1"})
    mock_jira_client.get_issues.return_value = [story]

    await jira_story_missing_assignee_warning_task()

    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_story_missing_assignee_warning_already_warned(mock_jira_client, mock_settings):
    story = MockIssue("PROJ1-1", assignee=None)
    mock_jira_client.get_issues.return_value = [story]
    mock_jira_client.get_comments.return_value = [
        MockComment("<!-- AUTO_GENERATED_JIRA_STORY_MISSING_ASSIGNEE_WARNING -->")
    ]

    await jira_story_missing_assignee_warning_task()

    mock_jira_client.add_comment.assert_not_called()
