import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_missing_labels_warning_task
import app.tasks

@pytest.fixture(autouse=True)
def mock_gitlab_env(mocker):
    # This is to mock everything the task uses locally
    # It seems in tasks.py we do:
    # from app.clients import settings
    # We must patch it exactly where it's being used.
    # The actual string might be `app.tasks.settings` because of `from app.clients import settings` in tasks.py
    # But wait, it's inside the function: `from app.clients import settings`
    pass

@pytest.mark.asyncio
async def test_missing_labels_adds_warning(mocker):
    # Patch the settings inside app.clients since that's where it's imported from
    mock_settings = mocker.patch("app.clients.settings", autospec=False)
    mock_settings.get.return_value = "project1"

    mock_client_cls = mocker.patch("app.clients.gitlab_client.GitLabClient")
    mock_gitlab_client = MagicMock()
    mock_client_cls.return_value = mock_gitlab_client

    mock_project = MagicMock()
    mock_gitlab_client.client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.labels = []

    mock_note = MagicMock()
    mock_note.body = "some other comment"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project.mergerequests.list.return_value = [mock_mr]

    result = await gitlab_mr_missing_labels_warning_task()
    assert "warned 1 MRs" in result
    mock_gitlab_client.create_mr_note.assert_called_once()
    assert "<!-- AUTO_GENERATED_GITLAB_MR_MISSING_LABELS_WARNING -->" in mock_gitlab_client.create_mr_note.call_args[0][2]

@pytest.mark.asyncio
async def test_missing_labels_already_warned(mocker):
    mock_settings = mocker.patch("app.clients.settings", autospec=False)
    mock_settings.get.return_value = "project1"

    mock_client_cls = mocker.patch("app.clients.gitlab_client.GitLabClient")
    mock_gitlab_client = MagicMock()
    mock_client_cls.return_value = mock_gitlab_client

    mock_project = MagicMock()
    mock_gitlab_client.client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.iid = 2
    mock_mr.labels = []

    mock_note = MagicMock()
    mock_note.body = "<!-- AUTO_GENERATED_GITLAB_MR_MISSING_LABELS_WARNING -->\nWarning"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project.mergerequests.list.return_value = [mock_mr]

    result = await gitlab_mr_missing_labels_warning_task()
    assert "warned 0 MRs" in result
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_has_labels_no_warning(mocker):
    mock_settings = mocker.patch("app.clients.settings", autospec=False)
    mock_settings.get.return_value = "project1"

    mock_client_cls = mocker.patch("app.clients.gitlab_client.GitLabClient")
    mock_gitlab_client = MagicMock()
    mock_client_cls.return_value = mock_gitlab_client

    mock_project = MagicMock()
    mock_gitlab_client.client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.iid = 3
    mock_mr.labels = ["bug"]

    mock_project.mergerequests.list.return_value = [mock_mr]

    result = await gitlab_mr_missing_labels_warning_task()
    assert "warned 0 MRs" in result
    mock_gitlab_client.create_mr_note.assert_not_called()
