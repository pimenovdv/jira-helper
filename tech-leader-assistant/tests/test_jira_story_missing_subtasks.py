import pytest
from unittest.mock import MagicMock
from app.tasks import jira_story_missing_subtasks_warning_task

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.tasks.settings")
    original_get = mock.get

    class MockSettings:
        def __init__(self):
            self._project_key = "TEST-PROJ"

        def get(self, key, default=None):
            if key == "JIRA_PROJECT_KEY":
                return self._project_key
            return None

    mock_inst = MockSettings()
    mock.get.side_effect = mock_inst.get

    mock_client = mocker.patch("app.clients.settings")
    mock_client.get.side_effect = mock_inst.get

    return mock_inst

@pytest.fixture(autouse=True)
def mock_jira(mocker):
    return mocker.patch("app.clients.jira_client.JIRA")

@pytest.fixture
def mock_jira_client(mocker):
    mock = mocker.patch("app.tasks.JiraClient")
    client_instance = MagicMock()
    mock.return_value = client_instance
    return client_instance

@pytest.mark.asyncio
async def test_jira_story_missing_subtasks_warning_task_no_project(mock_settings, mock_jira_client):
    mock_settings._project_key = None
    res = await jira_story_missing_subtasks_warning_task()
    assert "aborted" in res
    mock_jira_client.search_issues.assert_not_called()

@pytest.mark.asyncio
async def test_jira_story_missing_subtasks_warning_task_has_subtasks(mock_settings, mock_jira_client):
    story = MagicMock()
    story.key = "TEST-1"

    subtask = MagicMock()
    story.fields.subtasks = [subtask]

    mock_jira_client.search_issues.return_value = [story]

    res = await jira_story_missing_subtasks_warning_task()

    assert "Warned on 0 Stories" in res
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_story_missing_subtasks_warning_task_already_warned(mock_settings, mock_jira_client):
    story = MagicMock()
    story.key = "TEST-1"
    story.fields.subtasks = []

    comment = MagicMock()
    comment.body = "<!-- AUTO_GENERATED_STORY_MISSING_SUBTASKS_WARNING -->\nblabla"

    mock_jira_client.search_issues.return_value = [story]
    mock_jira_client.get_comments.return_value = [comment]

    res = await jira_story_missing_subtasks_warning_task()

    assert "Warned on 0 Stories" in res
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_story_missing_subtasks_warning_task_success(mock_settings, mock_jira_client):
    story = MagicMock()
    story.key = "TEST-1"
    story.fields.subtasks = []

    mock_jira_client.search_issues.return_value = [story]
    mock_jira_client.get_comments.return_value = []
    mock_jira_client.add_comment.return_value = True

    res = await jira_story_missing_subtasks_warning_task()

    assert "Warned on 1 Stories" in res
    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "TEST-1"
    assert "<!-- AUTO_GENERATED_STORY_MISSING_SUBTASKS_WARNING -->" in args[1]
    assert "This Story currently has no subtasks linked" in args[1]
