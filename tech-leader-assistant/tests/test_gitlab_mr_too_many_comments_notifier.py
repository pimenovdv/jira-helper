import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_too_many_comments_notifier_task

@pytest.fixture
def mock_gitlab_client(mocker):
    # Mock settings by patching the imported object inside the task module
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = "project-1"

    # Mock GitLabClient class where it is used in app.tasks
    mock_gl_client_cls = mocker.patch("app.tasks.GitLabClient")
    mock_client_instance = mock_gl_client_cls.return_value

    return mock_client_instance


@pytest.mark.asyncio
async def test_gitlab_mr_too_many_comments_notifier_task_sends_reminder(mock_gitlab_client):
    mock_project = MagicMock()
    mock_gitlab_client.client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.iid = 123
    mock_project.mergerequests.list.return_value = [mock_mr]

    # 16 discussions, all resolvable
    discussions = []
    for i in range(16):
        d = MagicMock()
        d.attributes = {'notes': [{'resolvable': True}]}
        discussions.append(d)

    mock_mr.discussions.list.return_value = discussions

    # Empty notes to simulate no previous reminder
    mock_mr.notes.list.return_value = []

    await gitlab_mr_too_many_comments_notifier_task()

    mock_gitlab_client.create_mr_note.assert_called_once()
    args, _ = mock_gitlab_client.create_mr_note.call_args
    assert args[0] == "project-1"
    assert args[1] == 123
    assert "<!-- AUTO_GENERATED_TOO_MANY_COMMENTS -->" in args[2]

@pytest.mark.asyncio
async def test_gitlab_mr_too_many_comments_notifier_task_already_reminded(mock_gitlab_client):
    mock_project = MagicMock()
    mock_gitlab_client.client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.iid = 456
    mock_project.mergerequests.list.return_value = [mock_mr]

    # 16 discussions, all resolvable
    discussions = []
    for i in range(16):
        d = MagicMock()
        d.attributes = {'notes': [{'resolvable': True}]}
        discussions.append(d)

    mock_mr.discussions.list.return_value = discussions

    # Note with marker
    mock_note = MagicMock()
    mock_note.body = "reminder here <!-- AUTO_GENERATED_TOO_MANY_COMMENTS -->"
    mock_mr.notes.list.return_value = [mock_note]

    await gitlab_mr_too_many_comments_notifier_task()

    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_too_many_comments_notifier_task_under_threshold(mock_gitlab_client):
    mock_project = MagicMock()
    mock_gitlab_client.client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.iid = 789
    mock_project.mergerequests.list.return_value = [mock_mr]

    # Only 10 discussions
    discussions = []
    for i in range(10):
        d = MagicMock()
        d.attributes = {'notes': [{'resolvable': True}]}
        discussions.append(d)

    mock_mr.discussions.list.return_value = discussions
    mock_mr.notes.list.return_value = []

    await gitlab_mr_too_many_comments_notifier_task()

    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_too_many_comments_notifier_task_non_resolvable_discussions(mock_gitlab_client):
    mock_project = MagicMock()
    mock_gitlab_client.client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.iid = 101
    mock_project.mergerequests.list.return_value = [mock_mr]

    # 20 discussions, but all non-resolvable (e.g. system notes)
    discussions = []
    for i in range(20):
        d = MagicMock()
        d.attributes = {'notes': [{'resolvable': False}]}
        discussions.append(d)

    mock_mr.discussions.list.return_value = discussions
    mock_mr.notes.list.return_value = []

    await gitlab_mr_too_many_comments_notifier_task()

    mock_gitlab_client.create_mr_note.assert_not_called()
