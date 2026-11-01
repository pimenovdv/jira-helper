import pytest
from unittest.mock import MagicMock
import app.tasks

@pytest.fixture(autouse=True)
def mock_jira_base(mocker):
    mocker.patch("app.clients.jira_client.JIRA")

@pytest.fixture
def mock_jira_client(mocker):
    return mocker.patch("app.clients.jira_client.JiraClient")

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.clients.settings")
    mock.get.side_effect = lambda k, d=None: {
        "JIRA_TRACKED_PROJECTS": "TESTPROJ",
        "JIRA_STORY_POINTS_FIELD": "customfield_10016"
    }.get(k, d)
    return mock

class MockComment:
    def __init__(self, body):
        self.body = body

class MockIssue:
    def __init__(self, key, points=None, assignee_id=None):
        self.key = key
        class Fields:
            pass
        self.fields = Fields()
        if points is not None:
            self.fields.customfield_10016 = points
        if assignee_id is not None:
            class Assignee:
                accountId = assignee_id
            self.fields.assignee = Assignee()

@pytest.mark.asyncio
async def test_jira_story_missing_story_points_warning(mock_jira_client, mock_settings, mocker):
    client_instance = mock_jira_client.return_value

    issue1 = MockIssue("TEST-1")
    issue2 = MockIssue("TEST-2", assignee_id="user123")
    issue3 = MockIssue("TEST-3", points=5)
    issue4 = MockIssue("TEST-4")

    client_instance.search_issues.return_value = [issue1, issue2, issue3, issue4]

    def mock_get_comments(issue_key):
        if issue_key == "TEST-4":
            return [MockComment("<!-- AUTO_GENERATED_JIRA_STORY_MISSING_STORY_POINTS_WARNING -->")]
        return []

    client_instance.get_comments.side_effect = mock_get_comments

    result = await app.tasks.jira_story_missing_story_points_warning_task()

    assert "Warned 2 stories" in result

    client_instance.search_issues.assert_called_once_with('project = "TESTPROJ" AND issuetype = "Story" AND statusCategory != Done')

    assert client_instance.add_comment.call_count == 2

    call1 = client_instance.add_comment.call_args_list[0]
    assert call1[0][0] == "TEST-1"
    assert "⚠️ This Story is missing story points estimation." in call1[0][1]

    call2 = client_instance.add_comment.call_args_list[1]
    assert call2[0][0] == "TEST-2"
    assert "⚠️ [~accountid:user123], This Story is missing story points estimation." in call2[0][1]
