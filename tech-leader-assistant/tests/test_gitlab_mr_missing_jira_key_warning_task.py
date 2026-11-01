import pytest
from unittest.mock import MagicMock, call
from app.tasks import gitlab_mr_missing_jira_key_warning_task

@pytest.fixture
def mock_gitlab_client(mocker):
    # Because GitLabClient is imported inside the function context:
    # `from app.clients.gitlab_client import GitLabClient`
    # We must patch it at the source, `app.clients.gitlab_client.GitLabClient`,
    # otherwise the local import will bypass the mock in `app.tasks`.
    return mocker.patch("app.clients.gitlab_client.GitLabClient")

@pytest.fixture
def mock_settings(mocker):
    # We patch app.tasks.settings because in app/tasks.py it is imported as:
    # from app.clients import settings
    # But in other places it is done differently.
    # Let's just mock both to be safe.
    mocker.patch("app.clients.settings")
    return mocker.patch("app.tasks.settings")

@pytest.mark.asyncio
async def test_gitlab_mr_missing_jira_key_adds_comment(mock_gitlab_client, mock_settings, mocker):
    mock_settings_local = mocker.patch("app.clients.settings")
    mock_settings_local.get.return_value = "proj-1"
    mock_gl_instance = mock_gitlab_client.return_value

    mock_mr_no_key = MagicMock()
    mock_mr_no_key.iid = 101
    mock_mr_no_key.title = "Add a new feature"

    mock_gl_instance.get_project_merge_requests.return_value = [mock_mr_no_key]

    # Mock specific MR object and its notes
    mock_project = MagicMock()
    mock_mr_obj = MagicMock()
    mock_mr_obj.iid = 101
    mock_note = MagicMock()
    mock_note.body = "Some regular comment"
    mock_mr_obj.notes.list.return_value = [mock_note]

    mock_project.mergerequests.get.return_value = mock_mr_obj
    mock_gl_instance.client.projects.get.return_value = mock_project

    # Execute
    result = await gitlab_mr_missing_jira_key_warning_task()

    # Assert
    assert "warned 1 MRs" in result
    mock_mr_obj.notes.create.assert_called_once()
    call_arg = mock_mr_obj.notes.create.call_args[0][0]
    assert "<!-- AUTO_GENERATED_GITLAB_MR_MISSING_JIRA_KEY_WARNING -->" in call_arg['body']
    assert "добавь ключ задачи Jira" in call_arg['body']

@pytest.mark.asyncio
async def test_gitlab_mr_has_jira_key_no_comment(mock_gitlab_client, mocker):
    # Setup
    mock_settings_local = mocker.patch("app.clients.settings")
    mock_settings_local.get.return_value = "proj-1"
    mock_gl_instance = mock_gitlab_client.return_value

    mock_mr_with_key = MagicMock()
    mock_mr_with_key.iid = 102
    mock_mr_with_key.title = "PROJ-123: Add a new feature"

    mock_gl_instance.get_project_merge_requests.return_value = [mock_mr_with_key]

    # Execute
    result = await gitlab_mr_missing_jira_key_warning_task()

    # Assert
    assert "warned 0 MRs" in result
    mock_gl_instance.client.projects.get.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_jira_key_already_warned(mock_gitlab_client, mocker):
    # Setup
    mock_settings_local = mocker.patch("app.clients.settings")
    mock_settings_local.get.return_value = "proj-1"
    mock_gl_instance = mock_gitlab_client.return_value

    mock_mr_no_key = MagicMock()
    mock_mr_no_key.iid = 103
    mock_mr_no_key.title = "Fix typo"

    mock_gl_instance.get_project_merge_requests.return_value = [mock_mr_no_key]

    # Mock specific MR object and its notes (with warning)
    mock_project = MagicMock()
    mock_mr_obj = MagicMock()
    mock_mr_obj.iid = 103
    mock_note = MagicMock()
    mock_note.body = "<!-- AUTO_GENERATED_GITLAB_MR_MISSING_JIRA_KEY_WARNING -->\nWarning!"
    mock_mr_obj.notes.list.return_value = [mock_note]

    mock_project.mergerequests.get.return_value = mock_mr_obj
    mock_gl_instance.client.projects.get.return_value = mock_project

    # Execute
    result = await gitlab_mr_missing_jira_key_warning_task()

    # Assert
    assert "warned 0 MRs" in result
    mock_mr_obj.notes.create.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_jira_key_exception_handling(mock_gitlab_client, mocker):
    # Setup
    mock_settings_local = mocker.patch("app.clients.settings")
    mock_settings_local.get.return_value = "proj-1"
    mock_gl_instance = mock_gitlab_client.return_value
    mock_gl_instance.get_project_merge_requests.side_effect = Exception("API failure")

    # Execute
    result = await gitlab_mr_missing_jira_key_warning_task()

    # Assert
    assert "warned 0 MRs" in result
