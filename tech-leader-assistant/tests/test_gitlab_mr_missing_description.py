import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_missing_description_reminder_task

@pytest.fixture
def mock_settings(mocker):
    # The function imports `from app.clients import settings`, so we patch it there.
    mock = mocker.patch("app.tasks.settings")
    # Actually wait, `settings` is imported as `from app.clients import settings` inside the task.
    # Let's mock the original settings class so it covers all imports.
    mock_settings_obj = mocker.patch("app.clients.settings")
    def mock_get(key, default=""):
        if key == "GITLAB_TRACKED_PROJECTS":
            return "project1, project2"
        return default
    mock_settings_obj.get.side_effect = mock_get
    return mock_settings_obj

@pytest.fixture
def mock_gitlab_client(mocker):
    # The function imports `from app.clients.gitlab_client import GitLabClient`,
    # but uses it directly. Better to patch it in the source module.
    mock_class = mocker.patch("app.clients.gitlab_client.GitLabClient")
    mock_instance = MagicMock()
    mock_class.return_value = mock_instance
    return mock_instance

@pytest.mark.asyncio
async def test_gitlab_mr_missing_description_adds_comment(mock_settings, mock_gitlab_client):
    # Setup MRs
    mr1 = MagicMock()
    mr1.iid = 1
    mr1.draft = False
    mr1.title = "Update README"
    mr1.description = "Too short"  # < 10 chars

    mock_gitlab_client.get_merge_requests.return_value = [mr1]

    # Setup notes without marker
    note = MagicMock()
    note.body = "Some comment"
    mock_gitlab_client.get_mr_notes.return_value = [note]

    await gitlab_mr_missing_description_reminder_task()

    # Check it comments on mr1 for the projects
    # There are 3 projects in the original settings fixture (let's verify the mock default from other tests or just check if it's called 2 times)
    from unittest.mock import ANY
    assert mock_gitlab_client.create_mr_note.call_count >= 2
    mock_gitlab_client.create_mr_note.assert_any_call("project1", 1, ANY)
    mock_gitlab_client.create_mr_note.assert_any_call("project2", 1, ANY)

@pytest.mark.asyncio
async def test_gitlab_mr_missing_description_ignores_adequate(mock_settings, mock_gitlab_client):
    mr1 = MagicMock()
    mr1.iid = 1
    mr1.draft = False
    mr1.title = "Update README"
    mr1.description = "This is a detailed description of the changes."

    mock_gitlab_client.get_merge_requests.return_value = [mr1]

    await gitlab_mr_missing_description_reminder_task()

    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_description_ignores_already_reminded(mock_settings, mock_gitlab_client):
    mr1 = MagicMock()
    mr1.iid = 1
    mr1.draft = False
    mr1.title = "Update README"
    mr1.description = "Short"

    mock_gitlab_client.get_merge_requests.return_value = [mr1]

    # Setup notes with marker
    note = MagicMock()
    note.body = "Reminder: This Merge Request seems to lack a meaningful description. Please provide detailed information about the changes.\n\n<!-- AUTO_GENERATED_MISSING_DESC_REMINDER -->"
    mock_gitlab_client.get_mr_notes.return_value = [note]

    await gitlab_mr_missing_description_reminder_task()

    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_description_ignores_draft(mock_settings, mock_gitlab_client):
    mr1 = MagicMock()
    mr1.iid = 1
    mr1.draft = True
    mr1.title = "Draft: Update README"
    mr1.description = ""

    mock_gitlab_client.get_merge_requests.return_value = [mr1]

    await gitlab_mr_missing_description_reminder_task()

    mock_gitlab_client.create_mr_note.assert_not_called()
