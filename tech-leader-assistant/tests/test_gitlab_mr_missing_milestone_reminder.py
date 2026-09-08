import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_missing_milestone_reminder_task

@pytest.fixture
def mock_settings(mocker):
    settings_mock = mocker.patch("app.tasks.settings")
    settings_mock.get.side_effect = lambda k, default=None: "project1" if k == "GITLAB_TRACKED_PROJECTS" else "fake_key" if k == "OPENAI_API_KEY" else default
    return settings_mock

@pytest.fixture
def mock_gitlab_client(mocker):
    client_mock = mocker.patch("app.tasks.GitLabClient").return_value
    return client_mock

@pytest.fixture
def mock_chat_openai(mocker):
    llm_mock = mocker.patch("app.tasks.ChatOpenAI").return_value
    llm_mock.ainvoke = mocker.AsyncMock()
    llm_mock.ainvoke.return_value.content = "Test milestone reminder comment."
    return llm_mock

@pytest.mark.asyncio
async def test_gitlab_mr_missing_milestone_no_api_key(mocker):
    settings_mock = mocker.patch("app.tasks.settings")
    settings_mock.get.side_effect = lambda k, default=None: "" if k == "OPENAI_API_KEY" else default

    result = await gitlab_mr_missing_milestone_reminder_task()
    assert result == "GitLab MR missing milestone reminder task skipped (no OpenAI API key)"

@pytest.mark.asyncio
async def test_gitlab_mr_missing_milestone_has_milestone(mock_settings, mock_gitlab_client, mock_chat_openai):
    mr_mock = MagicMock()
    mr_mock.draft = False
    mr_mock.title = "Feature"
    mr_mock.iid = 1
    # Has a milestone
    mr_mock.milestone = {"id": 10}
    mock_gitlab_client.get_merge_requests.return_value = [mr_mock]

    result = await gitlab_mr_missing_milestone_reminder_task()

    assert result == "GitLab MR missing milestone reminder task completed."
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_milestone_already_reminded(mock_settings, mock_gitlab_client, mock_chat_openai):
    mr_mock = MagicMock()
    mr_mock.draft = False
    mr_mock.title = "Feature"
    mr_mock.iid = 1
    mr_mock.milestone = None

    note_mock = MagicMock()
    note_mock.body = "Some text <!-- AUTO_GENERATED_MISSING_MILESTONE_REMINDER -->"
    mr_mock.notes.list.return_value = [note_mock]

    mock_gitlab_client.get_merge_requests.return_value = [mr_mock]

    result = await gitlab_mr_missing_milestone_reminder_task()

    assert result == "GitLab MR missing milestone reminder task completed."
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_milestone_sends_reminder(mock_settings, mock_gitlab_client, mock_chat_openai):
    mr_mock = MagicMock()
    mr_mock.draft = False
    mr_mock.title = "Feature"
    mr_mock.iid = 1
    mr_mock.milestone = None
    mr_mock.author = {"username": "test_author"}

    note_mock = MagicMock()
    note_mock.body = "Just a normal comment"
    mr_mock.notes.list.return_value = [note_mock]

    mock_gitlab_client.get_merge_requests.return_value = [mr_mock]

    result = await gitlab_mr_missing_milestone_reminder_task()

    assert result == "GitLab MR missing milestone reminder task completed."
    mock_chat_openai.ainvoke.assert_called_once()
    mock_gitlab_client.create_mr_note.assert_called_once_with(
        "project1",
        1,
        "Test milestone reminder comment.\n\n<!-- AUTO_GENERATED_MISSING_MILESTONE_REMINDER -->"
    )
