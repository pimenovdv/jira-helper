import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_missing_target_branch_validator_task

@pytest.mark.asyncio
async def test_gitlab_mr_missing_target_branch_validator_task(mocker):
    mock_settings = MagicMock()
    mock_settings.get.return_value = "1"
    mocker.patch("app.clients.settings", mock_settings)

    mock_gitlab = MagicMock()
    mocker.patch("app.tasks.GitLabClient", return_value=mock_gitlab)

    mock_project = MagicMock()
    mock_gitlab.client.projects.get.return_value = mock_project

    mock_mr1 = MagicMock()
    mock_mr1.iid = 1
    mock_mr1.target_branch = "main"
    mock_mr1.labels = []
    mock_mr1.author = {"username": "testuser"}
    mock_mr1.notes.list.return_value = []

    mock_mr2 = MagicMock()
    mock_mr2.iid = 2
    mock_mr2.target_branch = "develop"
    mock_mr2.labels = []
    mock_mr2.author = {"username": "testuser2"}
    mock_mr2.notes.list.return_value = []

    mock_mr3 = MagicMock()
    mock_mr3.iid = 3
    mock_mr3.target_branch = "main"
    mock_mr3.labels = ["direct-main-merge"]
    mock_mr3.author = {"username": "testuser3"}
    mock_mr3.notes.list.return_value = []

    mock_project.mergerequests.list.return_value = [mock_mr1, mock_mr2, mock_mr3]

    await gitlab_mr_missing_target_branch_validator_task()

    mock_mr1.notes.create.assert_called_once()
    assert "AUTO_GENERATED_MISSING_TARGET_BRANCH_VALIDATOR_WARNING" in mock_mr1.notes.create.call_args[0][0]["body"]

    mock_mr2.notes.create.assert_not_called()
    mock_mr3.notes.create.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_target_branch_already_warned(mocker):
    mock_settings = MagicMock()
    mock_settings.get.return_value = "1"
    mocker.patch("app.clients.settings", mock_settings)

    mock_gitlab = MagicMock()
    mocker.patch("app.tasks.GitLabClient", return_value=mock_gitlab)

    mock_project = MagicMock()
    mock_gitlab.client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.target_branch = "main"
    mock_mr.labels = []

    mock_note = MagicMock()
    mock_note.body = "<!-- AUTO_GENERATED_MISSING_TARGET_BRANCH_VALIDATOR_WARNING -->"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project.mergerequests.list.return_value = [mock_mr]

    await gitlab_mr_missing_target_branch_validator_task()

    mock_mr.notes.create.assert_not_called()
