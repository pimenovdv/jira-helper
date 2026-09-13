import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_missing_release_notes_checker_task

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.tasks.settings")
    mock.get.side_effect = lambda k, d="": {
        "OPENAI_API_KEY": "test-key",
        "GITLAB_TRACKED_PROJECTS": "123",
    }.get(k, d)
    return mock

@pytest.fixture
def mock_gitlab_client(mocker):
    mock = mocker.patch("app.tasks.GitLabClient")
    instance = mock.return_value
    instance.client.projects.get.return_value = MagicMock()
    return instance

@pytest.fixture
def mock_llm(mocker):
    mock_chat = mocker.patch("app.tasks.ChatOpenAI")
    instance = mock_chat.return_value
    mock_response = MagicMock()
    mock_response.content = "Please add release notes. <!-- AUTO_GENERATED_MISSING_RELEASE_NOTES_COMMENT -->"
    instance.ainvoke = mocker.AsyncMock(return_value=mock_response)
    return instance

@pytest.mark.asyncio
async def test_missing_release_notes_added(mock_settings, mock_gitlab_client, mock_llm):
    project_mock = mock_gitlab_client.client.projects.get.return_value
    mr_mock = MagicMock()
    mr_mock.iid = 1
    mr_mock.title = "feat: add new button"
    mr_mock.description = "This PR adds a button."
    mr_mock.draft = False
    mr_mock.author = {"username": "johndoe"}

    notes_mock = MagicMock()
    # No existing notes
    mr_mock.notes.list.return_value = []

    project_mock.mergerequests.list.return_value = [mr_mock]

    result = await gitlab_mr_missing_release_notes_checker_task()

    assert "completed" in result
    mock_llm.ainvoke.assert_awaited_once()
    mock_gitlab_client.create_mr_note.assert_called_once_with(
        "123", 1, "Please add release notes. <!-- AUTO_GENERATED_MISSING_RELEASE_NOTES_COMMENT -->"
    )

@pytest.mark.asyncio
async def test_skip_draft(mock_settings, mock_gitlab_client, mock_llm):
    project_mock = mock_gitlab_client.client.projects.get.return_value
    mr_mock = MagicMock()
    mr_mock.iid = 1
    mr_mock.title = "Draft: feat: add new button"
    mr_mock.description = "This PR adds a button."
    mr_mock.draft = True

    project_mock.mergerequests.list.return_value = [mr_mock]

    result = await gitlab_mr_missing_release_notes_checker_task()

    assert "completed" in result
    mock_llm.ainvoke.assert_not_called()
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_skip_non_user_facing(mock_settings, mock_gitlab_client, mock_llm):
    project_mock = mock_gitlab_client.client.projects.get.return_value
    mr_mock = MagicMock()
    mr_mock.iid = 1
    mr_mock.title = "chore: update dependencies"
    mr_mock.description = "update bumps"
    mr_mock.draft = False

    project_mock.mergerequests.list.return_value = [mr_mock]

    result = await gitlab_mr_missing_release_notes_checker_task()

    assert "completed" in result
    mock_llm.ainvoke.assert_not_called()
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_skip_already_has_release_notes_in_desc(mock_settings, mock_gitlab_client, mock_llm):
    project_mock = mock_gitlab_client.client.projects.get.return_value
    mr_mock = MagicMock()
    mr_mock.iid = 1
    mr_mock.title = "feat: add user profile"
    mr_mock.description = "## Release Notes\nAdded user profile"
    mr_mock.draft = False

    project_mock.mergerequests.list.return_value = [mr_mock]

    result = await gitlab_mr_missing_release_notes_checker_task()

    assert "completed" in result
    mock_llm.ainvoke.assert_not_called()
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_skip_already_reminded(mock_settings, mock_gitlab_client, mock_llm):
    project_mock = mock_gitlab_client.client.projects.get.return_value
    mr_mock = MagicMock()
    mr_mock.iid = 1
    mr_mock.title = "feat: add user profile"
    mr_mock.description = "Just some info"
    mr_mock.draft = False

    note_mock = MagicMock()
    note_mock.body = "Please add release notes. <!-- AUTO_GENERATED_MISSING_RELEASE_NOTES_COMMENT -->"
    mr_mock.notes.list.return_value = [note_mock]

    project_mock.mergerequests.list.return_value = [mr_mock]

    result = await gitlab_mr_missing_release_notes_checker_task()

    assert "completed" in result
    mock_llm.ainvoke.assert_not_called()
    mock_gitlab_client.create_mr_note.assert_not_called()
