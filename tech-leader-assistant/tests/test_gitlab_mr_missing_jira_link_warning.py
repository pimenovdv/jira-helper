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
    mock_settings.get.return_value = "PROJ1"

    mock_client = MagicMock()
    mock_gitlab_client.return_value.client = mock_client

    mock_project = MagicMock()
    mock_client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.title = "Update README"
    mock_mr.description = "Just updating readme"
    mock_mr.iid = 1
    mock_project.mergerequests.list.return_value = [mock_mr]

    mock_discussion = MagicMock()
    mock_discussion.attributes = {'notes': [{'body': 'regular comment'}]}
    mock_mr.discussions.list.return_value = [mock_discussion]

    await gitlab_mr_missing_jira_link_warning_task()

    mock_mr.notes.create.assert_called_once()
    call_args = mock_mr.notes.create.call_args[0]
    assert "missing a Jira issue key" in call_args[0]['body']
    assert "<!-- AUTO_GENERATED_GITLAB_MR_MISSING_JIRA_LINK_WARNING -->" in call_args[0]['body']

@pytest.mark.asyncio
async def test_gitlab_mr_missing_jira_link_warning_task_has_link(mock_gitlab_client, mock_settings):
    mock_settings.get.return_value = "PROJ1"

    mock_client = MagicMock()
    mock_gitlab_client.return_value.client = mock_client

    mock_project = MagicMock()
    mock_client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.title = "PROJ-123 Update README"
    mock_mr.description = "Just updating readme"
    mock_mr.iid = 1
    mock_project.mergerequests.list.return_value = [mock_mr]

    await gitlab_mr_missing_jira_link_warning_task()

    mock_mr.notes.create.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_jira_link_warning_task_already_commented(mock_gitlab_client, mock_settings):
    mock_settings.get.return_value = "PROJ1"

    mock_client = MagicMock()
    mock_gitlab_client.return_value.client = mock_client

    mock_project = MagicMock()
    mock_client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.title = "Update README"
    mock_mr.description = "Just updating readme"
    mock_mr.iid = 1
    mock_project.mergerequests.list.return_value = [mock_mr]

    mock_discussion = MagicMock()
    mock_discussion.attributes = {'notes': [{'body': '<!-- AUTO_GENERATED_GITLAB_MR_MISSING_JIRA_LINK_WARNING -->'}]}
    mock_mr.discussions.list.return_value = [mock_discussion]

    await gitlab_mr_missing_jira_link_warning_task()

    mock_mr.notes.create.assert_not_called()
