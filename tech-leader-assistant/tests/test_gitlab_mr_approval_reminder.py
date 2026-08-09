import pytest
import datetime
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_approval_reminder_task
from app import tasks

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch.object(tasks, "settings")
    mock.get.side_effect = lambda k, d="": "sk-test" if k == "OPENAI_API_KEY" else "1" if k == "GITLAB_TRACKED_PROJECTS" else d
    return mock

@pytest.fixture
def mock_gitlab_client(mocker):
    mock_cls = mocker.patch.object(tasks, "GitLabClient")
    mock_instance = mock_cls.return_value
    return mock_instance

@pytest.mark.asyncio
async def test_gitlab_mr_approval_reminder_task_success(mock_settings, mock_gitlab_client, mocker):
    mock_mr = MagicMock()
    mock_mr.draft = False
    mock_mr.iid = 100
    mock_mr.has_conflicts = False
    # created 3 days ago
    mock_mr.created_at = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=3)).isoformat()
    mock_mr.reviewers = [{"username": "reviewer1"}]

    # successful pipeline
    mock_pipeline = MagicMock()
    mock_pipeline.status = "success"
    mock_mr.pipelines.list.return_value = [mock_pipeline]

    # no unresolved threads
    mock_mr.discussions.list.return_value = []

    # no approvals
    mock_approvals = MagicMock()
    mock_approvals.approved_by = []
    mock_mr.approvals.get.return_value = mock_approvals

    # no previous note
    mock_mr.notes.list.return_value = []

    mock_gitlab_client.get_merge_requests.return_value = [mock_mr]

    res = await gitlab_mr_approval_reminder_task()

    mock_gitlab_client.create_mr_note.assert_called_once()
    args = mock_gitlab_client.create_mr_note.call_args[0]
    assert args[0] == "1"
    assert args[1] == 100
    assert "AUTO_GENERATED_GITLAB_MR_APPROVAL_REMINDER" in args[2]
    assert "@reviewer1" in args[2]
    assert "completed" in res

@pytest.mark.asyncio
async def test_gitlab_mr_approval_reminder_task_skip_draft(mock_settings, mock_gitlab_client, mocker):
    mock_mr = MagicMock()
    mock_mr.draft = True
    mock_gitlab_client.get_merge_requests.return_value = [mock_mr]

    await gitlab_mr_approval_reminder_task()
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_approval_reminder_task_skip_recently_created(mock_settings, mock_gitlab_client, mocker):
    mock_mr = MagicMock()
    mock_mr.draft = False
    mock_mr.created_at = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
    mock_gitlab_client.get_merge_requests.return_value = [mock_mr]

    await gitlab_mr_approval_reminder_task()
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_approval_reminder_task_skip_unresolved(mock_settings, mock_gitlab_client, mocker):
    mock_mr = MagicMock()
    mock_mr.draft = False
    mock_mr.has_conflicts = False
    mock_mr.created_at = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=3)).isoformat()

    mock_pipeline = MagicMock()
    mock_pipeline.status = "success"
    mock_mr.pipelines.list.return_value = [mock_pipeline]

    mock_disc = MagicMock()
    mock_disc.attributes = {"notes": [{"resolvable": True, "resolved": False}]}
    mock_mr.discussions.list.return_value = [mock_disc]

    mock_gitlab_client.get_merge_requests.return_value = [mock_mr]

    await gitlab_mr_approval_reminder_task()
    mock_gitlab_client.create_mr_note.assert_not_called()
