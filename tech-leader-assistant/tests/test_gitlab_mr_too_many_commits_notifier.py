import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_too_many_commits_notifier_task

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.tasks.settings")
    mock.get.return_value = "project-1"
    return mock

@pytest.fixture
def mock_gitlab_client(mocker):
    return mocker.patch("app.tasks.GitLabClient")

@pytest.mark.asyncio
async def test_gitlab_mr_too_many_commits_notifier_adds_note(mock_settings, mock_gitlab_client):
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.commits.return_value = iter([MagicMock()] * 21)

    mock_note = MagicMock()
    mock_note.body = "Some existing note"
    mock_mr.notes.list.return_value = [mock_note]

    mock_gitlab_client.get_open_mrs.return_value = [mock_mr]

    result = await gitlab_mr_too_many_commits_notifier_task()

    assert result == "GitLab MR too many commits notifier task completed"
    mock_gitlab_client.create_mr_note.assert_called_once()
    args, _ = mock_gitlab_client.create_mr_note.call_args
    assert args[0] == "project-1"
    assert args[1] == 1
    assert "Too Many Commits Warning" in args[2]

@pytest.mark.asyncio
async def test_gitlab_mr_too_many_commits_notifier_no_action_if_few_commits(mock_settings, mock_gitlab_client):
    mock_mr = MagicMock()
    mock_mr.iid = 2
    mock_mr.commits.return_value = iter([MagicMock()] * 10)

    mock_gitlab_client.get_open_mrs.return_value = [mock_mr]

    result = await gitlab_mr_too_many_commits_notifier_task()

    assert result == "GitLab MR too many commits notifier task completed"
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_too_many_commits_notifier_already_warned(mock_settings, mock_gitlab_client):
    mock_mr = MagicMock()
    mock_mr.iid = 3
    mock_mr.commits.return_value = iter([MagicMock()] * 25)

    mock_note = MagicMock()
    mock_note.body = "<!-- AUTO_GENERATED_TOO_MANY_COMMITS_WARNING -->\nExisting warning"
    mock_mr.notes.list.return_value = [mock_note]

    mock_gitlab_client.get_open_mrs.return_value = [mock_mr]

    result = await gitlab_mr_too_many_commits_notifier_task()

    assert result == "GitLab MR too many commits notifier task completed"
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_too_many_commits_notifier_no_projects_tracked(mock_settings, mock_gitlab_client):
    mock_settings.get.return_value = ""

    result = await gitlab_mr_too_many_commits_notifier_task()

    assert result == "Too many commits notifier task skipped (no projects tracked)"
    mock_gitlab_client.get_open_mrs.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_too_many_commits_notifier_error_handling(mock_settings, mock_gitlab_client):
    mock_gitlab_client.get_open_mrs.side_effect = Exception("Test exception")

    result = await gitlab_mr_too_many_commits_notifier_task()

    assert result == "GitLab MR too many commits notifier task completed"
