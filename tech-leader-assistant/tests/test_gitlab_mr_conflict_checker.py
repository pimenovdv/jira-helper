import pytest
import logging
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_conflict_checker_task

@pytest.fixture
def mock_settings(mocker):
    # Mock settings globally
    mock = mocker.patch("app.tasks.settings")
    mock.get.side_effect = lambda key, default="": {
        "OPENAI_API_KEY": "test_key",
        "GITLAB_TRACKED_PROJECTS": "123",
    }.get(key, default)
    return mock

@pytest.fixture
def mock_gitlab_client_class(mocker):
    # Mock the GitLabClient class
    return mocker.patch("app.tasks.GitLabClient")

@pytest.fixture
def mock_chat_openai(mocker):
    return mocker.patch("app.tasks.ChatOpenAI")

@pytest.mark.asyncio
async def test_conflict_checker_no_api_key(mocker, mock_settings):
    mock_settings.get.side_effect = lambda key, default="": "" if key == "OPENAI_API_KEY" else "123"
    result = await gitlab_mr_conflict_checker_task()
    assert result == "GitLab MR conflict checker task skipped (no OpenAI API key)"

@pytest.mark.asyncio
async def test_conflict_checker_no_projects(mocker, mock_settings):
    mock_settings.get.side_effect = lambda key, default="": "test_key" if key == "OPENAI_API_KEY" else ""
    result = await gitlab_mr_conflict_checker_task()
    assert result == "No projects tracked"

@pytest.mark.asyncio
async def test_conflict_checker_mr_with_conflicts_no_comment(mocker, mock_settings, mock_gitlab_client_class, mock_chat_openai):
    # Setup GitLab Client mock
    mock_client = mock_gitlab_client_class.return_value
    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.has_conflicts = True

    mock_note = MagicMock()
    mock_note.body = "Some other comment"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project.mergerequests.list.return_value = [mock_mr]
    mock_client.client.projects.get.return_value = mock_project

    # Setup LLM mock
    mock_llm_instance = mock_chat_openai.return_value
    mock_response = MagicMock()
    mock_response.content = "Please resolve conflicts."
    mock_llm_instance.ainvoke = mocker.AsyncMock(return_value=mock_response)

    result = await gitlab_mr_conflict_checker_task()

    assert result == "GitLab MR conflict checker task completed"
    mock_llm_instance.ainvoke.assert_awaited_once()
    mock_client.create_mr_note.assert_called_once_with(
        "123",
        1,
        "<!-- AUTO_GENERATED_GITLAB_MR_CONFLICT_CHECKER -->\nPlease resolve conflicts."
    )

@pytest.mark.asyncio
async def test_conflict_checker_mr_with_conflicts_already_commented(mocker, mock_settings, mock_gitlab_client_class, mock_chat_openai):
    # Setup GitLab Client mock
    mock_client = mock_gitlab_client_class.return_value
    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.has_conflicts = True

    mock_note = MagicMock()
    mock_note.body = "<!-- AUTO_GENERATED_GITLAB_MR_CONFLICT_CHECKER -->\nPlease resolve conflicts."
    mock_mr.notes.list.return_value = [mock_note]

    mock_project.mergerequests.list.return_value = [mock_mr]
    mock_client.client.projects.get.return_value = mock_project

    # Setup LLM mock
    mock_llm_instance = mock_chat_openai.return_value
    mock_llm_instance.ainvoke = mocker.AsyncMock()

    result = await gitlab_mr_conflict_checker_task()

    assert result == "GitLab MR conflict checker task completed"
    mock_llm_instance.ainvoke.assert_not_called()
    mock_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_conflict_checker_mr_no_conflicts(mocker, mock_settings, mock_gitlab_client_class, mock_chat_openai):
    # Setup GitLab Client mock
    mock_client = mock_gitlab_client_class.return_value
    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.has_conflicts = False

    mock_project.mergerequests.list.return_value = [mock_mr]
    mock_client.client.projects.get.return_value = mock_project

    # Setup LLM mock
    mock_llm_instance = mock_chat_openai.return_value
    mock_llm_instance.ainvoke = mocker.AsyncMock()

    result = await gitlab_mr_conflict_checker_task()

    assert result == "GitLab MR conflict checker task completed"
    mock_llm_instance.ainvoke.assert_not_called()
    mock_client.create_mr_note.assert_not_called()
