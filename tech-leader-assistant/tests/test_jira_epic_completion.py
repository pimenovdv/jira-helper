import pytest
from unittest.mock import MagicMock, ANY
from app.tasks import jira_epic_completion_checker_task

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.tasks.settings")
    mock_settings_obj = mocker.patch("app.clients.settings")
    def mock_get(key, default=""):
        if key == "JIRA_TRACKED_PROJECTS":
            return "PROJ1"
        return default
    mock_settings_obj.get.side_effect = mock_get
    return mock_settings_obj

@pytest.fixture
def mock_jira_client(mocker):
    mock_class = mocker.patch("app.clients.jira_client.JiraClient")
    mock_instance = MagicMock()
    mock_class.return_value = mock_instance
    return mock_instance

@pytest.mark.asyncio
async def test_jira_epic_completion_adds_comment(mock_settings, mock_jira_client):
    epic = MagicMock()
    epic.key = "PROJ1-100"

    # Mock search_issues
    # First call: epics. Second call: children of PROJ1-100.
    child1 = MagicMock()
    child1.fields.status.statusCategory.name = "Done"
    child2 = MagicMock()
    child2.fields.status.statusCategory.name = "Done"

    mock_jira_client.search_issues.side_effect = [
        [epic], # epics search
        [child1, child2] # children search
    ]

    # Setup comments without marker
    comment = MagicMock()
    comment.body = "Some comment"
    mock_jira_client.get_comments.return_value = [comment]

    await jira_epic_completion_checker_task()

    mock_jira_client.add_comment.assert_called_once_with("PROJ1-100", ANY)

@pytest.mark.asyncio
async def test_jira_epic_completion_ignores_when_not_all_done(mock_settings, mock_jira_client):
    epic = MagicMock()
    epic.key = "PROJ1-100"

    child1 = MagicMock()
    child1.fields.status.statusCategory.name = "Done"
    child2 = MagicMock()
    child2.fields.status.statusCategory.name = "In Progress"

    mock_jira_client.search_issues.side_effect = [
        [epic],
        [child1, child2]
    ]

    await jira_epic_completion_checker_task()

    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_epic_completion_ignores_already_reminded(mock_settings, mock_jira_client):
    epic = MagicMock()
    epic.key = "PROJ1-100"

    child1 = MagicMock()
    child1.fields.status.statusCategory.name = "Done"

    mock_jira_client.search_issues.side_effect = [
        [epic],
        [child1]
    ]

    comment = MagicMock()
    comment.body = "Reminder: All child issues for this Epic are completed. Please consider marking this Epic as Done.\n\n<!-- AUTO_GENERATED_EPIC_COMPLETION_REMINDER -->"
    mock_jira_client.get_comments.return_value = [comment]

    await jira_epic_completion_checker_task()

    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_epic_completion_ignores_no_children(mock_settings, mock_jira_client):
    epic = MagicMock()
    epic.key = "PROJ1-100"

    mock_jira_client.search_issues.side_effect = [
        [epic],
        [] # No children
    ]

    await jira_epic_completion_checker_task()

    mock_jira_client.add_comment.assert_not_called()
