import pytest
from unittest.mock import MagicMock
from app.tasks import jira_story_missing_description_warning_task

@pytest.fixture(autouse=True)
def mock_jira_init(mocker):
    # Mock JIRA client initialization to avoid real connection attempts during test setup
    mocker.patch('app.clients.jira_client.JIRA')

@pytest.fixture
def mock_jira_client(mocker):
    return mocker.patch("app.clients.jira_client.JiraClient")

@pytest.fixture
def mock_settings(mocker):
    # Do not use autospec=True for Dynaconf settings as .get is handled dynamically
    mock_set = mocker.patch("app.tasks.settings")
    mock_set.get.return_value = "PROJ1"
    return mock_set

@pytest.mark.asyncio
async def test_jira_story_missing_description_warning_task_missing_description(mock_jira_client, mock_settings):
    # Setup
    jira_instance = mock_jira_client.return_value

    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.description = None

    jira_instance.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "A regular comment"
    jira_instance.get_comments.return_value = [mock_comment]

    # Execute
    result = await jira_story_missing_description_warning_task()

    # Assert
    jira_instance.search_issues.assert_called_once_with('project = "PROJ1" AND issuetype = "Story" AND statusCategory != Done')
    jira_instance.get_comments.assert_called_once_with("PROJ1-123")
    jira_instance.add_comment.assert_called_once()

    # Ensure our marker is in the warning message
    called_args = jira_instance.add_comment.call_args[0]
    assert "<!-- AUTO_GENERATED_STORY_MISSING_DESCRIPTION_WARNING -->" in called_args[1]

    assert result == "Jira story missing description warning task completed. Warned 1 stories."

@pytest.mark.asyncio
async def test_jira_story_missing_description_warning_task_has_description(mock_jira_client, mock_settings):
    # Setup
    jira_instance = mock_jira_client.return_value

    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-456"
    mock_issue.fields.description = "As a user, I want..."

    jira_instance.search_issues.return_value = [mock_issue]

    # Execute
    result = await jira_story_missing_description_warning_task()

    # Assert
    jira_instance.search_issues.assert_called_once()
    jira_instance.get_comments.assert_not_called()
    jira_instance.add_comment.assert_not_called()

    assert result == "Jira story missing description warning task completed. Warned 0 stories."

@pytest.mark.asyncio
async def test_jira_story_missing_description_warning_task_already_warned(mock_jira_client, mock_settings):
    # Setup
    jira_instance = mock_jira_client.return_value

    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-789"
    mock_issue.fields.description = "   " # effectively empty

    jira_instance.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "<!-- AUTO_GENERATED_STORY_MISSING_DESCRIPTION_WARNING -->\n⚠️ Warning"
    jira_instance.get_comments.return_value = [mock_comment]

    # Execute
    result = await jira_story_missing_description_warning_task()

    # Assert
    jira_instance.search_issues.assert_called_once()
    jira_instance.get_comments.assert_called_once_with("PROJ1-789")
    jira_instance.add_comment.assert_not_called()

    assert result == "Jira story missing description warning task completed. Warned 0 stories."

@pytest.mark.asyncio
async def test_jira_story_missing_description_warning_task_multiple_projects(mocker, mock_jira_client):
    # Setup
    mock_set = mocker.patch("app.tasks.settings")
    mock_set.get.return_value = "PROJ1, PROJ2"

    jira_instance = mock_jira_client.return_value
    jira_instance.search_issues.return_value = []

    # Execute
    result = await jira_story_missing_description_warning_task()

    # Assert
    assert jira_instance.search_issues.call_count == 2
    jira_instance.search_issues.assert_any_call('project = "PROJ1" AND issuetype = "Story" AND statusCategory != Done')
    jira_instance.search_issues.assert_any_call('project = "PROJ2" AND issuetype = "Story" AND statusCategory != Done')

    assert result == "Jira story missing description warning task completed. Warned 0 stories."
