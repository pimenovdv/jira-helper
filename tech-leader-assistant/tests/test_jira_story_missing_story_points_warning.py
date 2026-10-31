import pytest
from unittest.mock import MagicMock
from app.tasks import jira_story_missing_story_points_warning_task

@pytest.fixture
def mock_jira_client(mocker):
    return mocker.patch("app.clients.jira_client.JiraClient")

@pytest.fixture
def mock_settings(mocker):
    return mocker.patch("app.clients.settings", autospec=False)

@pytest.mark.asyncio
async def test_jira_story_missing_story_points_warning_task_adds_comment(mock_jira_client, mock_settings):
    mock_settings.get.return_value = "PROJ1"

    mock_jira = MagicMock()
    mock_jira_client.return_value = mock_jira

    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.customfield_10016 = None

    mock_jira.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "Some regular comment."
    mock_jira.get_comments.return_value = [mock_comment]

    await jira_story_missing_story_points_warning_task()

    mock_jira.add_comment.assert_called_once()
    call_args = mock_jira.add_comment.call_args[0]
    assert call_args[0] == "PROJ1-123"
    assert "missing an estimate in story points" in call_args[1]
    assert "<!-- AUTO_GENERATED_JIRA_STORY_MISSING_STORY_POINTS_WARNING -->" in call_args[1]

@pytest.mark.asyncio
async def test_jira_story_missing_story_points_warning_task_has_points(mock_jira_client, mock_settings):
    mock_settings.get.return_value = "PROJ1"

    mock_jira = MagicMock()
    mock_jira_client.return_value = mock_jira

    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.customfield_10016 = 5.0

    mock_jira.search_issues.return_value = [mock_issue]

    await jira_story_missing_story_points_warning_task()

    mock_jira.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_story_missing_story_points_warning_task_already_commented(mock_jira_client, mock_settings):
    mock_settings.get.return_value = "PROJ1"

    mock_jira = MagicMock()
    mock_jira_client.return_value = mock_jira

    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.customfield_10016 = None

    mock_jira.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "<!-- AUTO_GENERATED_JIRA_STORY_MISSING_STORY_POINTS_WARNING -->"
    mock_jira.get_comments.return_value = [mock_comment]

    await jira_story_missing_story_points_warning_task()

    mock_jira.add_comment.assert_not_called()
