import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_draft_labeler_task
from app.clients import settings

@pytest.fixture(autouse=True)
def setup_settings():
    original_projects = settings.get("GITLAB_TRACKED_PROJECTS")
    settings.set("GITLAB_TRACKED_PROJECTS", "project_1")
    yield
    settings.set("GITLAB_TRACKED_PROJECTS", original_projects)

@pytest.fixture
def mock_gitlab_client(mocker):
    # Mock GitLabClient
    mock_client = MagicMock()
    mocker.patch("app.tasks.GitLabClient", return_value=mock_client)
    return mock_client

@pytest.mark.asyncio
async def test_draft_label_added(mock_gitlab_client):
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.title = "Draft: My cool feature"
    mock_mr.labels = ["enhancement"]

    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr]

    await gitlab_draft_labeler_task()

    mock_gitlab_client.update_mr_labels.assert_called_once_with(
        "project_1", 1, ["enhancement", "status: draft"]
    )

@pytest.mark.asyncio
async def test_draft_label_removed(mock_gitlab_client):
    mock_mr = MagicMock()
    mock_mr.iid = 2
    mock_mr.title = "Feature: My cool feature"
    mock_mr.labels = ["enhancement", "status: draft"]

    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr]

    await gitlab_draft_labeler_task()

    mock_gitlab_client.update_mr_labels.assert_called_once_with(
        "project_1", 2, ["enhancement"]
    )

@pytest.mark.asyncio
async def test_draft_label_no_change_needed(mock_gitlab_client):
    mock_mr1 = MagicMock()
    mock_mr1.iid = 1
    mock_mr1.title = "Draft: Feature"
    mock_mr1.labels = ["status: draft"]

    mock_mr2 = MagicMock()
    mock_mr2.iid = 2
    mock_mr2.title = "Feature"
    mock_mr2.labels = []

    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr1, mock_mr2]

    await gitlab_draft_labeler_task()

    # Should not call update_mr_labels since states are already correct
    mock_gitlab_client.update_mr_labels.assert_not_called()
