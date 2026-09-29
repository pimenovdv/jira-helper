import pytest
from datetime import datetime, timezone, timedelta
from app.tasks import gitlab_mr_stale_needs_work_reminder_task

@pytest.fixture(autouse=True)
def mock_gitlab_client_global(mocker):
    # It is imported locally inside the function!
    # So we MUST patch `app.tasks.GitLabClient` or maybe `app.clients.gitlab_client.GitLabClient`.
    # Let's patch both just in case, but since it's `from app.clients.gitlab_client import GitLabClient`,
    # inside `gitlab_mr_stale_needs_work_reminder_task`, it imports it locally.
    # Therefore, we need to patch `app.clients.gitlab_client.GitLabClient`.
    mock_gitlab_client_cls = mocker.patch("app.clients.gitlab_client.GitLabClient")
    mock_instance = mocker.MagicMock()
    mock_gitlab_client_cls.return_value = mock_instance
    return mock_instance

@pytest.fixture(autouse=True)
def mock_settings_global(mocker):
    # It also imports settings locally: `from app.clients import settings`
    mock_settings = mocker.patch("app.clients.settings")
    config = {
        "OPENAI_API_KEY": "test-key",
        "GITLAB_TRACKED_PROJECTS": "proj1"
    }
    mock_settings.get.side_effect = lambda key, default="": config.get(key, default)
    return mock_settings

@pytest.mark.asyncio
async def test_gitlab_mr_stale_needs_work_reminder_task_posts_comment(mocker, mock_gitlab_client_global):
    mock_llm = mocker.MagicMock()
    mock_llm.ainvoke = mocker.AsyncMock(return_value=mocker.MagicMock(content="Please address feedback."))
    # Also ChatOpenAI is imported locally! `from langchain_openai import ChatOpenAI`
    mocker.patch("langchain_openai.ChatOpenAI", return_value=mock_llm)

    mock_project = mocker.MagicMock()

    mock_mr = mocker.MagicMock()
    mock_mr.iid = 1
    mock_mr.labels = ["needs work"]
    mock_mr.author = {"username": "test_user"}

    mock_commit = mocker.MagicMock()
    old_date = datetime.now(timezone.utc) - timedelta(days=4)
    mock_commit.created_at = old_date.isoformat()
    mock_mr.commits.return_value = [mock_commit]

    mock_notes_manager = mocker.MagicMock()
    mock_notes_manager.list.return_value = []
    mock_mr.notes = mock_notes_manager

    mock_mr_manager = mocker.MagicMock()
    mock_mr_manager.list.return_value = [mock_mr]
    mock_project.mergerequests = mock_mr_manager

    mock_gitlab_client_global.client.projects.get.return_value = mock_project

    result = await gitlab_mr_stale_needs_work_reminder_task()

    assert result == "GitLab MR stale needs work reminder task completed."
    mock_gitlab_client_global.create_mr_note.assert_called_once_with(
        "proj1", 1, "Please address feedback.\n\n<!-- AUTO_GENERATED_GITLAB_STALE_NEEDS_WORK_REMINDER -->"
    )

@pytest.mark.asyncio
async def test_gitlab_mr_stale_needs_work_reminder_task_no_comment_if_recent_commit(mocker, mock_gitlab_client_global):
    mock_project = mocker.MagicMock()

    mock_mr = mocker.MagicMock()
    mock_mr.iid = 1
    mock_mr.labels = ["changes requested"]

    mock_commit = mocker.MagicMock()
    recent_date = datetime.now(timezone.utc) - timedelta(days=1)
    mock_commit.created_at = recent_date.isoformat()
    mock_mr.commits.return_value = [mock_commit]

    mock_mr_manager = mocker.MagicMock()
    mock_mr_manager.list.return_value = [mock_mr]
    mock_project.mergerequests = mock_mr_manager

    mock_gitlab_client_global.client.projects.get.return_value = mock_project

    mocker.patch("langchain_openai.ChatOpenAI")

    await gitlab_mr_stale_needs_work_reminder_task()

    mock_gitlab_client_global.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_stale_needs_work_reminder_task_no_comment_if_no_label(mocker, mock_gitlab_client_global):
    mock_project = mocker.MagicMock()

    mock_mr = mocker.MagicMock()
    mock_mr.iid = 1
    mock_mr.labels = ["bug"]

    mock_mr_manager = mocker.MagicMock()
    mock_mr_manager.list.return_value = [mock_mr]
    mock_project.mergerequests = mock_mr_manager

    mock_gitlab_client_global.client.projects.get.return_value = mock_project

    mocker.patch("langchain_openai.ChatOpenAI")

    await gitlab_mr_stale_needs_work_reminder_task()

    mock_mr.commits.assert_not_called()
    mock_gitlab_client_global.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_stale_needs_work_reminder_task_already_notified(mocker, mock_gitlab_client_global):
    mock_project = mocker.MagicMock()

    mock_mr = mocker.MagicMock()
    mock_mr.iid = 1
    mock_mr.labels = ["needs work"]

    mock_commit = mocker.MagicMock()
    old_date = datetime.now(timezone.utc) - timedelta(days=4)
    mock_commit.created_at = old_date.isoformat()
    mock_mr.commits.return_value = [mock_commit]

    mock_note = mocker.MagicMock()
    mock_note.body = "some text <!-- AUTO_GENERATED_GITLAB_STALE_NEEDS_WORK_REMINDER -->"

    mock_notes_manager = mocker.MagicMock()
    mock_notes_manager.list.return_value = [mock_note]
    mock_mr.notes = mock_notes_manager

    mock_mr_manager = mocker.MagicMock()
    mock_mr_manager.list.return_value = [mock_mr]
    mock_project.mergerequests = mock_mr_manager

    mock_gitlab_client_global.client.projects.get.return_value = mock_project

    mocker.patch("langchain_openai.ChatOpenAI")

    await gitlab_mr_stale_needs_work_reminder_task()

    mock_gitlab_client_global.create_mr_note.assert_not_called()
