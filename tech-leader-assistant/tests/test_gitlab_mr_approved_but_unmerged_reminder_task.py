import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_approved_but_unmerged_reminder_task

@pytest.fixture
def mock_dependencies(mocker):
    # Patch at the source since tasks.py has a local import
    mock_gitlab = mocker.patch("app.clients.gitlab_client.GitLabClient")
    mock_settings = mocker.patch("app.tasks.settings")
    mock_chatopenai = mocker.patch("langchain_openai.ChatOpenAI")

    # We will need mock_llm for ChatOpenAI return value
    mock_llm = mocker.MagicMock()
    mock_chatopenai.return_value = mock_llm

    mock_settings.get.side_effect = lambda k, default=None: "project1" if k == "GITLAB_TRACKED_PROJECTS" else "fake_key"

    return mock_gitlab, mock_llm

@pytest.mark.asyncio
async def test_gitlab_mr_approved_but_unmerged_reminder_task_posts_comment(mock_dependencies, mocker):
    mock_gitlab, mock_llm = mock_dependencies

    client_instance = mock_gitlab.return_value
    mock_gitlab_client_prop = mocker.MagicMock()
    client_instance.client = mock_gitlab_client_prop
    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.has_conflicts = False
    mock_mr.updated_at = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()

    mock_approvals = MagicMock()
    mock_approvals.approvals_left = 0
    mock_mr.approvals.get.return_value = mock_approvals

    mock_mr.notes.list.return_value = []

    mock_project.mergerequests.list.return_value = [mock_mr]
    client_instance.client.projects.get.return_value = mock_project
    # Ensure we don't make network calls
    mocker.patch("gitlab.Gitlab")


    mock_resp = MagicMock()
    mock_resp.content = "Reminder message"
    mock_llm.ainvoke = mocker.AsyncMock(return_value=mock_resp)

    await gitlab_mr_approved_but_unmerged_reminder_task()

    client_instance.create_mr_note.assert_called_once()
    args = client_instance.create_mr_note.call_args[0]
    assert args[0] == "project1"
    assert args[1] == 1
    assert "Reminder message" in args[2]
    assert "<!-- AUTO_GENERATED_GITLAB_APPROVED_UNMERGED_REMINDER -->" in args[2]


@pytest.mark.asyncio
async def test_gitlab_mr_approved_but_unmerged_reminder_task_skips_recent_mr(mock_dependencies, mocker):
    mock_gitlab, _ = mock_dependencies

    client_instance = mock_gitlab.return_value
    mock_gitlab_client_prop = mocker.MagicMock()
    client_instance.client = mock_gitlab_client_prop
    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.has_conflicts = False
    # Updated 1 day ago - should be skipped
    mock_mr.updated_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    mock_approvals = MagicMock()
    mock_approvals.approvals_left = 0
    mock_mr.approvals.get.return_value = mock_approvals

    mock_project.mergerequests.list.return_value = [mock_mr]
    client_instance.client.projects.get.return_value = mock_project
    # Ensure we don't make network calls
    mocker.patch("gitlab.Gitlab")


    await gitlab_mr_approved_but_unmerged_reminder_task()

    client_instance.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_approved_but_unmerged_reminder_task_skips_unapproved_mr(mock_dependencies, mocker):
    mock_gitlab, _ = mock_dependencies

    client_instance = mock_gitlab.return_value
    mock_gitlab_client_prop = mocker.MagicMock()
    client_instance.client = mock_gitlab_client_prop
    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.has_conflicts = False
    mock_mr.updated_at = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()

    mock_approvals = MagicMock()
    mock_approvals.approvals_left = 1 # Not fully approved
    mock_mr.approvals.get.return_value = mock_approvals

    mock_project.mergerequests.list.return_value = [mock_mr]
    client_instance.client.projects.get.return_value = mock_project
    # Ensure we don't make network calls
    mocker.patch("gitlab.Gitlab")


    await gitlab_mr_approved_but_unmerged_reminder_task()

    client_instance.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_approved_but_unmerged_reminder_task_skips_conflicted_mr(mock_dependencies, mocker):
    mock_gitlab, _ = mock_dependencies

    client_instance = mock_gitlab.return_value
    mock_gitlab_client_prop = mocker.MagicMock()
    client_instance.client = mock_gitlab_client_prop
    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.has_conflicts = True # Has conflicts
    mock_mr.updated_at = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()

    mock_approvals = MagicMock()
    mock_approvals.approvals_left = 0
    mock_mr.approvals.get.return_value = mock_approvals

    mock_project.mergerequests.list.return_value = [mock_mr]
    client_instance.client.projects.get.return_value = mock_project
    # Ensure we don't make network calls
    mocker.patch("gitlab.Gitlab")


    await gitlab_mr_approved_but_unmerged_reminder_task()

    client_instance.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_approved_but_unmerged_reminder_task_skips_already_commented(mock_dependencies, mocker):
    mock_gitlab, _ = mock_dependencies

    client_instance = mock_gitlab.return_value
    mock_gitlab_client_prop = mocker.MagicMock()
    client_instance.client = mock_gitlab_client_prop
    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.has_conflicts = False
    mock_mr.updated_at = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()

    mock_approvals = MagicMock()
    mock_approvals.approvals_left = 0
    mock_mr.approvals.get.return_value = mock_approvals

    mock_note = MagicMock()
    mock_note.body = "Some comment <!-- AUTO_GENERATED_GITLAB_APPROVED_UNMERGED_REMINDER -->"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project.mergerequests.list.return_value = [mock_mr]
    client_instance.client.projects.get.return_value = mock_project
    # Ensure we don't make network calls
    mocker.patch("gitlab.Gitlab")


    await gitlab_mr_approved_but_unmerged_reminder_task()

    client_instance.create_mr_note.assert_not_called()
