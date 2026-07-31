import pytest
from app.tasks import gitlab_mr_missing_tests_notifier_task
from unittest.mock import MagicMock

@pytest.fixture
def mock_gitlab_client(mocker):
    return mocker.patch("app.tasks.GitLabClient")

@pytest.fixture
def mock_chat_openai(mocker):
    return mocker.patch("app.tasks.ChatOpenAI")

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.tasks.settings")
    mock.get.side_effect = lambda key, default="": {
        "OPENAI_API_KEY": "test-key",
        "GITLAB_TRACKED_PROJECTS": "123,456",
    }.get(key, default)
    return mock

@pytest.mark.asyncio
async def test_gitlab_mr_missing_tests_notifier_task_success(mock_gitlab_client, mock_chat_openai, mock_settings):
    # Setup GitLab Client mock
    mock_instance = mock_gitlab_client.return_value

    # Mock MR object from search
    mock_mr_search = MagicMock()
    mock_mr_search.iid = 1
    mock_instance.get_merge_requests.return_value = [mock_mr_search]

    # Mock Project object
    mock_gl_project = MagicMock()
    mock_instance.client.projects.get.return_value = mock_gl_project

    # Mock detailed MR object
    mock_full_mr = MagicMock()
    mock_full_mr.iid = 1
    mock_gl_project.mergerequests.get.return_value = mock_full_mr

    # Mock MR changes to have source code but no tests
    mock_full_mr.changes.return_value = {
        "changes": [
            {"new_path": "src/main.py"},
            {"new_path": "docs/readme.md"}
        ]
    }

    # Mock MR notes (no previous reminder)
    mock_note = MagicMock()
    mock_note.body = "Some comment"
    mock_full_mr.notes.list.return_value = [mock_note]

    # Setup LLM mock
    mock_llm_instance = mock_chat_openai.return_value
    mock_llm_response = MagicMock()
    mock_llm_response.content = "Пожалуйста, добавьте тесты."
    mock_llm_instance.invoke.return_value = mock_llm_response

    # Run the task
    result = await gitlab_mr_missing_tests_notifier_task()

    assert result == "GitLab MR missing tests notifier task completed"

    # Verify create_mr_note was called twice (once for each project 123 and 456)
    assert mock_instance.create_mr_note.call_count == 2

    call_args = mock_instance.create_mr_note.call_args_list[0][0]
    assert call_args[0] == "123" # project_id
    assert call_args[1] == 1 # mr_iid
    assert "Пожалуйста, добавьте тесты." in call_args[2]
    assert "<!-- AUTO_GENERATED_MR_MISSING_TESTS_NOTIFIER -->" in call_args[2]

@pytest.mark.asyncio
async def test_gitlab_mr_missing_tests_notifier_task_has_tests(mock_gitlab_client, mock_chat_openai, mock_settings):
    # Setup GitLab Client mock
    mock_instance = mock_gitlab_client.return_value
    mock_mr_search = MagicMock()
    mock_mr_search.iid = 1
    mock_instance.get_merge_requests.return_value = [mock_mr_search]

    mock_gl_project = MagicMock()
    mock_instance.client.projects.get.return_value = mock_gl_project

    mock_full_mr = MagicMock()
    mock_full_mr.iid = 1
    mock_gl_project.mergerequests.get.return_value = mock_full_mr

    # Mock MR changes to have both source and tests
    mock_full_mr.changes.return_value = {
        "changes": [
            {"new_path": "src/main.py"},
            {"new_path": "tests/test_main.py"}
        ]
    }

    # Run the task
    result = await gitlab_mr_missing_tests_notifier_task()

    assert result == "GitLab MR missing tests notifier task completed"

    # Verify create_mr_note was NOT called because tests exist
    mock_instance.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_tests_notifier_task_already_notified(mock_gitlab_client, mock_chat_openai, mock_settings):
    # Setup GitLab Client mock
    mock_instance = mock_gitlab_client.return_value
    mock_mr_search = MagicMock()
    mock_mr_search.iid = 1
    mock_instance.get_merge_requests.return_value = [mock_mr_search]

    mock_gl_project = MagicMock()
    mock_instance.client.projects.get.return_value = mock_gl_project

    mock_full_mr = MagicMock()
    mock_full_mr.iid = 1
    mock_gl_project.mergerequests.get.return_value = mock_full_mr

    # Mock MR changes to have source code but no tests
    mock_full_mr.changes.return_value = {
        "changes": [
            {"new_path": "src/main.py"}
        ]
    }

    # Mock MR notes (with previous reminder)
    mock_note = MagicMock()
    mock_note.body = "<!-- AUTO_GENERATED_MR_MISSING_TESTS_NOTIFIER -->"
    mock_full_mr.notes.list.return_value = [mock_note]

    # Run the task
    result = await gitlab_mr_missing_tests_notifier_task()

    assert result == "GitLab MR missing tests notifier task completed"

    # Verify create_mr_note was NOT called because reminder already exists
    mock_instance.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_tests_notifier_task_no_openai_key(mock_gitlab_client, mock_chat_openai, mocker):
    # Setup settings without OPENAI_API_KEY
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = ""

    # Run the task
    result = await gitlab_mr_missing_tests_notifier_task()

    assert result == "GitLab MR missing tests notifier task skipped (no OpenAI API key)"
    mock_gitlab_client.return_value.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_tests_notifier_task_project_fetch_error(mock_gitlab_client, mock_chat_openai, mock_settings):
    # Setup GitLab Client mock
    mock_instance = mock_gitlab_client.return_value
    mock_instance.get_merge_requests.return_value = []

    # Mock project fetch error
    mock_instance.client.projects.get.side_effect = Exception("API Error")

    # Run the task
    result = await gitlab_mr_missing_tests_notifier_task()

    assert result == "GitLab MR missing tests notifier task completed"
    mock_instance.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_tests_notifier_task_mr_fetch_error(mock_gitlab_client, mock_chat_openai, mock_settings):
    # Setup GitLab Client mock
    mock_instance = mock_gitlab_client.return_value
    mock_mr_search = MagicMock()
    mock_mr_search.iid = 1
    mock_instance.get_merge_requests.return_value = [mock_mr_search]

    mock_gl_project = MagicMock()
    mock_instance.client.projects.get.return_value = mock_gl_project

    # Mock MR fetch error
    mock_gl_project.mergerequests.get.side_effect = Exception("API Error")

    # Run the task
    result = await gitlab_mr_missing_tests_notifier_task()

    assert result == "GitLab MR missing tests notifier task completed"
    mock_instance.create_mr_note.assert_not_called()
