import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from app.tasks import gitlab_mr_missing_approvals_reminder_task

@pytest.fixture
def mock_settings(mocker):
    # Setup mock settings
    mock_s = MagicMock()
    mock_s.get.side_effect = lambda k, default="": {
        "GITLAB_TRACKED_PROJECTS": "123",
        "GITLAB_MR_MISSING_APPROVALS_DAYS": "3"
    }.get(k, default)
    # Patch settings in app.tasks and app.clients (where GitLabClient gets it)
    mocker.patch("app.tasks.settings", mock_s)
    mocker.patch("app.clients.settings", mock_s)
    mocker.patch("app.clients.gitlab_client.settings", mock_s)
    return mock_s

@pytest.fixture
def mock_gitlab_client(mocker):
    # We mock the GitLabClient instantiated in the task
    mock_gl_class = mocker.patch("app.tasks.GitLabClient")
    mock_instance = MagicMock()
    mock_gl_class.return_value = mock_instance
    return mock_instance

@pytest.mark.asyncio
async def test_gitlab_mr_missing_approvals_reminder_posts_comment(mock_settings, mock_gitlab_client, mocker):
    now = datetime.now(timezone.utc)
    old_date = (now - timedelta(days=4)).isoformat()

    mock_mr_data = MagicMock()
    mock_mr_data.iid = 1
    mock_mr_data.created_at = old_date
    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr_data]

    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.iid = 1
    # attributes is a dictionary, so get() should work.
    mock_mr.attributes = {"reviewers": [{"username": "johndoe"}]}

    mock_approvals = MagicMock()
    mock_approvals.approvals_left = 2
    mock_mr.approvals.get.return_value = mock_approvals

    mock_note = MagicMock()
    mock_note.body = "Some other comment"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project.mergerequests.get.return_value = mock_mr
    # Important: the tasks uses client.client.projects.get
    mock_client_client = MagicMock()
    mock_client_client.projects.get.return_value = mock_project
    mock_gitlab_client.client = mock_client_client

    await gitlab_mr_missing_approvals_reminder_task()

    mock_gitlab_client.create_mr_note.assert_called_once()
    args, _ = mock_gitlab_client.create_mr_note.call_args
    assert args[0] == "123"
    assert args[1] == 1
    assert "@johndoe" in args[2]
    assert "still requires 2 more approval" in args[2]
    assert "<!-- AUTO_GENERATED_MISSING_APPROVALS_REMINDER -->" in args[2]

@pytest.mark.asyncio
async def test_gitlab_mr_missing_approvals_reminder_skips_young_mr(mock_settings, mock_gitlab_client, mocker):
    now = datetime.now(timezone.utc)
    recent_date = (now - timedelta(days=1)).isoformat()

    mock_mr_data = MagicMock()
    mock_mr_data.iid = 1
    mock_mr_data.created_at = recent_date
    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr_data]

    await gitlab_mr_missing_approvals_reminder_task()

    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_approvals_reminder_skips_no_approvals_needed(mock_settings, mock_gitlab_client, mocker):
    now = datetime.now(timezone.utc)
    old_date = (now - timedelta(days=4)).isoformat()

    mock_mr_data = MagicMock()
    mock_mr_data.iid = 1
    mock_mr_data.created_at = old_date
    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr_data]

    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.iid = 1

    mock_approvals = MagicMock()
    mock_approvals.approvals_left = 0
    mock_mr.approvals.get.return_value = mock_approvals

    mock_project.mergerequests.get.return_value = mock_mr
    mock_client_client = MagicMock()
    mock_client_client.projects.get.return_value = mock_project
    mock_gitlab_client.client = mock_client_client

    await gitlab_mr_missing_approvals_reminder_task()

    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_approvals_reminder_skips_duplicate(mock_settings, mock_gitlab_client, mocker):
    now = datetime.now(timezone.utc)
    old_date = (now - timedelta(days=4)).isoformat()

    mock_mr_data = MagicMock()
    mock_mr_data.iid = 1
    mock_mr_data.created_at = old_date
    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr_data]

    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.iid = 1

    mock_approvals = MagicMock()
    mock_approvals.approvals_left = 1
    mock_mr.approvals.get.return_value = mock_approvals

    mock_note = MagicMock()
    mock_note.body = "<!-- AUTO_GENERATED_MISSING_APPROVALS_REMINDER -->"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project.mergerequests.get.return_value = mock_mr
    mock_client_client = MagicMock()
    mock_client_client.projects.get.return_value = mock_project
    mock_gitlab_client.client = mock_client_client

    await gitlab_mr_missing_approvals_reminder_task()

    mock_gitlab_client.create_mr_note.assert_not_called()
