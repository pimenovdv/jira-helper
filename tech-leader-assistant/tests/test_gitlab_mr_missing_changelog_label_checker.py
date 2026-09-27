import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_settings(mocker):
    def mock_get(key, default=""):
        if key == "GITLAB_TRACKED_PROJECTS":
            return "1,2"
        if key == "OPENAI_API_KEY":
            return "test_key"
        return default

    mock_settings_obj = MagicMock()
    mock_settings_obj.get.side_effect = mock_get
    mocker.patch("app.tasks.settings", mock_settings_obj)
    return mock_settings_obj

@pytest.fixture
def mock_gitlab_client(mocker):
    mock_client = MagicMock()
    mocker.patch("app.tasks.GitLabClient", return_value=mock_client)
    return mock_client

@pytest.fixture
def mock_chat_openai(mocker):
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Пожалуйста, добавьте метку changelog."
    mock_llm.ainvoke = mocker.AsyncMock(return_value=mock_response)
    return mock_llm

@pytest.mark.asyncio
async def test_gitlab_mr_missing_changelog_label_checker_success(mocker, mock_settings, mock_gitlab_client, mock_chat_openai):
    from app.tasks import gitlab_mr_missing_changelog_label_checker_task

    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.labels = ["bug"]
    mock_mr.author = {"username": "testuser"}

    mock_project.mergerequests.list.return_value = [mock_mr]

    mock_note = MagicMock()
    mock_note.body = "Random comment"
    mock_mr.notes.list.return_value = [mock_note]

    mock_gitlab_client.client.projects.get.return_value = mock_project

    mocker.patch("langchain_openai.ChatOpenAI", return_value=mock_chat_openai)

    result = await gitlab_mr_missing_changelog_label_checker_task()

    assert result == "GitLab MR missing changelog label checker task completed."
    mock_chat_openai.ainvoke.assert_awaited()
    assert mock_gitlab_client.create_mr_note.call_count == 2 # 2 projects tracked

@pytest.mark.asyncio
async def test_gitlab_mr_missing_changelog_label_checker_skip_has_label(mocker, mock_settings, mock_gitlab_client, mock_chat_openai):
    from app.tasks import gitlab_mr_missing_changelog_label_checker_task

    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.labels = ["Changelog:added", "feature"]

    mock_project.mergerequests.list.return_value = [mock_mr]
    mock_gitlab_client.client.projects.get.return_value = mock_project

    mocker.patch("langchain_openai.ChatOpenAI", return_value=mock_chat_openai)

    await gitlab_mr_missing_changelog_label_checker_task()

    mock_chat_openai.ainvoke.assert_not_called()
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_changelog_label_checker_already_notified(mocker, mock_settings, mock_gitlab_client, mock_chat_openai):
    from app.tasks import gitlab_mr_missing_changelog_label_checker_task

    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.labels = []

    mock_project.mergerequests.list.return_value = [mock_mr]

    mock_note = MagicMock()
    mock_note.body = "<!-- AUTO_GENERATED_GITLAB_MISSING_CHANGELOG_LABEL_REMINDER --> existing"
    mock_mr.notes.list.return_value = [mock_note]

    mock_gitlab_client.client.projects.get.return_value = mock_project

    mocker.patch("langchain_openai.ChatOpenAI", return_value=mock_chat_openai)

    await gitlab_mr_missing_changelog_label_checker_task()

    mock_chat_openai.ainvoke.assert_not_called()
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_changelog_label_checker_no_api_key(mocker):
    from app.tasks import gitlab_mr_missing_changelog_label_checker_task

    mock_settings_obj = MagicMock()
    mock_settings_obj.get.return_value = ""
    mocker.patch("app.tasks.settings", mock_settings_obj)

    result = await gitlab_mr_missing_changelog_label_checker_task()
    assert result == "GitLab MR missing changelog label checker task skipped (no OpenAI API key)"
