import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_secrets_scanner_task
from app import tasks

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch.object(tasks, "settings")
    mock.get.side_effect = lambda k, d="": "TESTPROJ" if k == "GITLAB_TRACKED_PROJECTS" else d
    return mock

@pytest.fixture
def mock_gitlab_client(mocker):
    # Setup GitLabClient mock
    mock_class = mocker.patch.object(tasks, "GitLabClient")
    instance = mock_class.return_value
    instance.client = MagicMock()
    return instance

@pytest.mark.asyncio
async def test_secrets_scanner_detects_secrets(mock_settings, mock_gitlab_client):
    # Setup MR list
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.notes.list.return_value = []
    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr]

    # Setup Full MR from API
    full_mr = MagicMock()
    # Provide a diff that has a secret
    changes_data = {
        'changes': [
            {
                'new_path': 'config.py',
                'diff': '@@ -1,2 +1,3 @@\n def get_config():\n+    api_key = "12345secret"\n     return config\n'
            }
        ]
    }
    full_mr.changes.return_value = changes_data
    mock_gitlab_client.client.projects.get.return_value.mergerequests.get.return_value = full_mr

    res = await gitlab_mr_secrets_scanner_task()

    assert "completed" in res
    mock_gitlab_client.create_mr_note.assert_called_once()
    args, _ = mock_gitlab_client.create_mr_note.call_args
    assert args[0] == "TESTPROJ"
    assert args[1] == 1
    assert "AUTO_GENERATED_SECRETS_SCANNER_WARNING" in args[2]
    assert "api_key = \"12345secret\"" in args[2]

@pytest.mark.asyncio
async def test_secrets_scanner_ignores_non_secrets(mock_settings, mock_gitlab_client):
    mock_mr = MagicMock()
    mock_mr.iid = 2
    mock_mr.notes.list.return_value = []
    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr]

    full_mr = MagicMock()
    changes_data = {
        'changes': [
            {
                'new_path': 'safe.txt',
                'diff': '@@ -1,2 +1,3 @@\n text\n+ This is safe\n'
            }
        ]
    }
    full_mr.changes.return_value = changes_data
    mock_gitlab_client.client.projects.get.return_value.mergerequests.get.return_value = full_mr

    res = await gitlab_mr_secrets_scanner_task()

    assert "completed" in res
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_secrets_scanner_ignores_already_warned(mock_settings, mock_gitlab_client):
    mock_mr = MagicMock()
    mock_mr.iid = 3
    # Existing note with marker
    mock_note = MagicMock()
    mock_note.body = "<!-- AUTO_GENERATED_SECRETS_SCANNER_WARNING -->"
    mock_mr.notes.list.return_value = [mock_note]

    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr]

    full_mr = MagicMock()
    changes_data = {
        'changes': [
            {
                'new_path': 'config.py',
                'diff': '@@ -1,2 +1,3 @@\n text\n+ password="root"\n'
            }
        ]
    }
    full_mr.changes.return_value = changes_data
    mock_gitlab_client.client.projects.get.return_value.mergerequests.get.return_value = full_mr

    res = await gitlab_mr_secrets_scanner_task()

    assert "completed" in res
    mock_gitlab_client.create_mr_note.assert_not_called()
