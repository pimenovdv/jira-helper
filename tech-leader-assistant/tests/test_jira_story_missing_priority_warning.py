import pytest
from unittest.mock import MagicMock
from app.tasks import jira_story_missing_priority_warning_task


class MockIssue:
    def __init__(self, key, priority=None):
        self.key = key
        self.fields = MagicMock()
        if priority is not None:
            self.fields.priority = priority
        else:
            del self.fields.priority


class MockComment:
    def __init__(self, body):
        self.body = body


@pytest.fixture
def mock_jira_client(mocker):
    mock_client = MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=mock_client)
    return mock_client


@pytest.fixture
def mock_settings(mocker):
    mock_settings_obj = MagicMock()
    mocker.patch("app.tasks.settings", mock_settings_obj)
    return mock_settings_obj


@pytest.mark.asyncio
async def test_jira_story_missing_priority_warning_sent(mock_jira_client, mock_settings):
    mock_settings.get.return_value = "PROJ1"

    issue = MockIssue(key="PROJ1-1") # missing priority
    mock_jira_client.get_issues.return_value = [issue]

    mock_jira_client.get_comments.return_value = [] # no previous warning

    await jira_story_missing_priority_warning_task()

    mock_jira_client.add_comment.assert_called_once()
    args, kwargs = mock_jira_client.add_comment.call_args
    assert args[0] == "PROJ1-1"
    assert "AUTO_GENERATED_JIRA_STORY_MISSING_PRIORITY_WARNING" in args[1]


@pytest.mark.asyncio
async def test_jira_story_missing_priority_has_priority(mock_jira_client, mock_settings):
    mock_settings.get.return_value = "PROJ1"

    issue = MockIssue(key="PROJ1-2", priority="High")
    mock_jira_client.get_issues.return_value = [issue]

    await jira_story_missing_priority_warning_task()

    mock_jira_client.add_comment.assert_not_called()


@pytest.mark.asyncio
async def test_jira_story_missing_priority_already_warned(mock_jira_client, mock_settings):
    mock_settings.get.return_value = "PROJ1"

    issue = MockIssue(key="PROJ1-3") # missing priority
    mock_jira_client.get_issues.return_value = [issue]

    mock_jira_client.get_comments.return_value = [MockComment(body="Previous comment with <!-- AUTO_GENERATED_JIRA_STORY_MISSING_PRIORITY_WARNING -->")]

    await jira_story_missing_priority_warning_task()

    mock_jira_client.add_comment.assert_not_called()
