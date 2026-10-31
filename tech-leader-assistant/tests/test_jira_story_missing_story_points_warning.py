import pytest
from unittest.mock import MagicMock
from app.tasks import jira_story_missing_story_points_warning_task

@pytest.fixture(autouse=True)
def mock_jira_client(mocker):
    # The function imports JiraClient locally:
    # from app.clients.jira_client import JiraClient
    # So we must patch it at "app.clients.jira_client.JiraClient"
    # AND because JiraClient wrapper has a search_issues method, we mock the wrapper.
    mock_class = mocker.patch("app.clients.jira_client.JiraClient")
    mock_jira = MagicMock()
    mock_class.return_value = mock_jira

    # Similarly, settings is imported locally:
    # from app.clients import settings
    # So we patch it at app.clients.settings
    mock_settings = mocker.patch("app.clients.settings")
    mock_settings.get.side_effect = lambda k, d="": "TEST" if "JIRA" in k else d

    return mock_jira

@pytest.mark.asyncio
async def test_jira_story_missing_story_points_warning_task_adds_comment(mock_jira_client):
    mock_issue = MagicMock()
    mock_issue.key = "TEST-1"
    mock_issue.fields = MagicMock()
    mock_issue.fields.customfield_10016 = None
    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "Some regular comment."
    mock_jira_client.get_comments.return_value = [mock_comment]

    await jira_story_missing_story_points_warning_task()

    mock_jira_client.search_issues.assert_called_once()
    mock_jira_client.get_comments.assert_called_once_with("TEST-1")
    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "TEST-1"
    assert "missing an estimate in story points" in args[1]
    assert "<!-- AUTO_GENERATED_JIRA_STORY_MISSING_STORY_POINTS_WARNING -->" in args[1]

@pytest.mark.asyncio
async def test_jira_story_missing_story_points_warning_task_already_warned(mock_jira_client):
    mock_issue = MagicMock()
    mock_issue.key = "TEST-2"
    mock_issue.fields = MagicMock()
    mock_issue.fields.customfield_10016 = None
    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "This is a warning <!-- AUTO_GENERATED_JIRA_STORY_MISSING_STORY_POINTS_WARNING -->"
    mock_jira_client.get_comments.return_value = [mock_comment]

    await jira_story_missing_story_points_warning_task()

    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_story_missing_story_points_warning_task_has_points(mock_jira_client):
    mock_issue = MagicMock()
    mock_issue.key = "TEST-3"
    mock_issue.fields = MagicMock()
    mock_issue.fields.customfield_10016 = 5.0
    mock_jira_client.search_issues.return_value = [mock_issue]

    await jira_story_missing_story_points_warning_task()

    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_story_missing_story_points_warning_task_zero_points(mock_jira_client):
    mock_issue = MagicMock()
    mock_issue.key = "TEST-4"
    mock_issue.fields = MagicMock()
    mock_issue.fields.customfield_10016 = 0.0
    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "Some regular comment."
    mock_jira_client.get_comments.return_value = [mock_comment]

    await jira_story_missing_story_points_warning_task()

    mock_jira_client.search_issues.assert_called_once()
    mock_jira_client.get_comments.assert_called_once_with("TEST-4")
    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "TEST-4"
    assert "missing an estimate in story points" in args[1]
    assert "<!-- AUTO_GENERATED_JIRA_STORY_MISSING_STORY_POINTS_WARNING -->" in args[1]
