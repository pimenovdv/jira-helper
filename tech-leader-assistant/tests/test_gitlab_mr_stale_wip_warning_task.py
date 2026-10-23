import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_stale_wip_warning_task

@pytest.fixture
def mock_settings(mocker):
    mock_set = mocker.patch("app.tasks.settings")
    mock_set.get.side_effect = lambda key, default="": {
        "OPENAI_API_KEY": "test_openai_key",
        "GITLAB_TRACKED_PROJECTS": "proj1",
    }.get(key, default)
    return mock_set

@pytest.fixture
def mock_gitlab_client(mocker):
    return mocker.patch("app.tasks.GitLabClient")

@pytest.fixture
def mock_chat_openai(mocker):
    return mocker.patch("app.tasks.ChatOpenAI")

@pytest.mark.asyncio
async def test_no_tracked_projects(mocker, mock_gitlab_client, mock_chat_openai):
    mock_set = mocker.patch("app.tasks.settings")
    mock_set.get.side_effect = lambda key, default="": {
        "OPENAI_API_KEY": "test_openai_key",
        "GITLAB_TRACKED_PROJECTS": "",
    }.get(key, default)

    await gitlab_mr_stale_wip_warning_task()

    mock_gitlab = mock_gitlab_client.return_value
    mock_gitlab.get_project_merge_requests.assert_not_called()

@pytest.mark.asyncio
async def test_mr_not_draft(mock_settings, mock_gitlab_client, mock_chat_openai):
    mock_gitlab = mock_gitlab_client.return_value

    mr_mock = MagicMock()
    mr_mock.title = "Feature: Test"
    mr_mock.draft = False

    mock_gitlab.get_project_merge_requests.return_value = [mr_mock]

    await gitlab_mr_stale_wip_warning_task()

    mock_gitlab.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_mr_draft_updated_recently(mock_settings, mock_gitlab_client, mock_chat_openai):
    mock_gitlab = mock_gitlab_client.return_value

    mr_mock = MagicMock()
    mr_mock.title = "Draft: Feature Test"
    mr_mock.draft = True
    recent_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    mr_mock.updated_at = recent_date

    mock_gitlab.get_project_merge_requests.return_value = [mr_mock]

    await gitlab_mr_stale_wip_warning_task()

    mock_gitlab.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_mr_draft_updated_long_ago_already_warned(mock_settings, mock_gitlab_client, mock_chat_openai):
    mock_gitlab = mock_gitlab_client.return_value

    mr_mock = MagicMock()
    mr_mock.title = "Draft: Feature Test"
    mr_mock.draft = True
    old_date = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    mr_mock.updated_at = old_date

    note_mock = MagicMock()
    note_mock.body = "Some comment\n\n<!-- AUTO_GENERATED_STALE_WIP_WARNING -->"

    notes_mock = MagicMock()
    notes_mock.list.return_value = [note_mock]
    mr_mock.notes = notes_mock

    mock_gitlab.get_project_merge_requests.return_value = [mr_mock]

    await gitlab_mr_stale_wip_warning_task()

    mock_gitlab.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_mr_draft_updated_long_ago_not_warned(mock_settings, mock_gitlab_client, mock_chat_openai):
    mock_gitlab = mock_gitlab_client.return_value
    mock_llm_instance = mock_chat_openai.return_value
    mock_llm_instance.invoke.return_value.content = "Please close or update."

    mr_mock = MagicMock()
    mr_mock.title = "Draft: Feature Test"
    mr_mock.draft = True
    old_date = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    mr_mock.updated_at = old_date
    mr_mock.author = {"username": "test_user"}
    mr_mock.iid = 123

    note_mock = MagicMock()
    note_mock.body = "Just a normal comment"

    notes_mock = MagicMock()
    notes_mock.list.return_value = [note_mock]
    mr_mock.notes = notes_mock

    mock_gitlab.get_project_merge_requests.return_value = [mr_mock]

    await gitlab_mr_stale_wip_warning_task()

    expected_body = "Please close or update.\n\n<!-- AUTO_GENERATED_STALE_WIP_WARNING -->"
    mock_gitlab.create_mr_note.assert_called_once_with("proj1", 123, expected_body)
