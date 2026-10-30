import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_missing_jira_link_warning_task

@pytest.fixture
def mock_gitlab_client(mocker):
    return mocker.patch("app.clients.gitlab_client.GitLabClient")

@pytest.fixture
def mock_settings(mocker):
    return mocker.patch("app.clients.settings", autospec=False)

@pytest.mark.asyncio
async def test_gitlab_mr_missing_jira_link_warning_task_adds_comment(mock_gitlab_client, mock_settings):
    mock_settings.get.return_value = "proj1"

    gl_instance = MagicMock()
    mock_gitlab_client.return_value.client = gl_instance

    mock_project = MagicMock()
    gl_instance.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.title = "Fix typo in README"
    mock_mr.description = "This PR fixes a typo."
    mock_mr.iid = 123

    mock_note = MagicMock()
    mock_note.body = "Some other comment"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project.mergerequests.list.return_value = [mock_mr]

    await gitlab_mr_missing_jira_link_warning_task()

    mock_mr.notes.create.assert_called_once()
    call_args = mock_mr.notes.create.call_args[0][0]
    assert "Warning: This Merge Request is missing a Jira issue link" in call_args["body"]
    assert "<!-- AUTO_GENERATED_GITLAB_MR_MISSING_JIRA_LINK_WARNING -->" in call_args["body"]

@pytest.mark.asyncio
async def test_gitlab_mr_missing_jira_link_warning_task_skips_if_jira_in_title(mock_gitlab_client, mock_settings):
    mock_settings.get.return_value = "proj1"

    gl_instance = MagicMock()
    mock_gitlab_client.return_value.client = gl_instance

    mock_project = MagicMock()
    gl_instance.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.title = "PROJ-123 Fix typo in README"
    mock_mr.description = "This PR fixes a typo."

    mock_project.mergerequests.list.return_value = [mock_mr]

    await gitlab_mr_missing_jira_link_warning_task()

    mock_mr.notes.create.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_jira_link_warning_task_skips_if_jira_in_description(mock_gitlab_client, mock_settings):
    mock_settings.get.return_value = "proj1"

    gl_instance = MagicMock()
    mock_gitlab_client.return_value.client = gl_instance

    mock_project = MagicMock()
    gl_instance.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.title = "Fix typo in README"
    mock_mr.description = "Fixes PROJ-456"

    mock_project.mergerequests.list.return_value = [mock_mr]

    await gitlab_mr_missing_jira_link_warning_task()

    mock_mr.notes.create.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_jira_link_warning_task_skips_if_already_commented(mock_gitlab_client, mock_settings):
    mock_settings.get.return_value = "proj1"

    gl_instance = MagicMock()
    mock_gitlab_client.return_value.client = gl_instance

    mock_project = MagicMock()
    gl_instance.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.title = "Fix typo in README"
    mock_mr.description = "This PR fixes a typo."
    mock_mr.iid = 123

    mock_note = MagicMock()
    mock_note.body = "<!-- AUTO_GENERATED_GITLAB_MR_MISSING_JIRA_LINK_WARNING -->"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project.mergerequests.list.return_value = [mock_mr]

    await gitlab_mr_missing_jira_link_warning_task()

    mock_mr.notes.create.assert_not_called()
