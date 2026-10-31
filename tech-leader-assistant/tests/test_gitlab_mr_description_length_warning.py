import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_description_length_warning_task

@pytest.fixture(autouse=True)
def mock_gl_client(mocker):
    mock_class = mocker.patch("app.clients.gitlab_client.GitLabClient")
    mock_gl = MagicMock()
    mock_class.return_value = mock_gl
    mock_settings = mocker.patch("app.clients.settings")
    mock_settings.get.side_effect = lambda k, d="": "TEST" if "GITLAB" in k else d
    mocker.patch("app.tasks.settings.get", side_effect=lambda k, d="": "TEST" if "GITLAB" in k else d)
    mocker.patch("app.tasks.GitLabClient", return_value=mock_gl)
    return mock_gl

@pytest.mark.asyncio
async def test_gitlab_mr_description_length_warning_adds_comment(mock_gl_client):
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.description = "Short desc" # < 20 chars
    mock_gl_client.get_merge_requests.return_value = [mock_mr]

    mock_note = MagicMock()
    mock_note.body = "Some regular comment."
    mock_mr.notes.list.return_value = [mock_note]

    await gitlab_mr_description_length_warning_task()

    mock_gl_client.get_merge_requests.assert_called_once_with("TEST", state="opened")
    mock_mr.notes.list.assert_called_once_with(get_all=True)
    mock_mr.notes.create.assert_called_once()
    args, _ = mock_mr.notes.create.call_args
    assert "description is very short" in args[0]["body"]
    assert "<!-- AUTO_GENERATED_GITLAB_MR_DESCRIPTION_LENGTH_WARNING -->" in args[0]["body"]

@pytest.mark.asyncio
async def test_gitlab_mr_description_length_warning_already_warned(mock_gl_client):
    mock_mr = MagicMock()
    mock_mr.iid = 2
    mock_mr.description = ""
    mock_gl_client.get_merge_requests.return_value = [mock_mr]

    mock_note = MagicMock()
    mock_note.body = "This is a warning <!-- AUTO_GENERATED_GITLAB_MR_DESCRIPTION_LENGTH_WARNING -->"
    mock_mr.notes.list.return_value = [mock_note]

    await gitlab_mr_description_length_warning_task()

    mock_mr.notes.create.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_description_length_warning_has_long_desc(mock_gl_client):
    mock_mr = MagicMock()
    mock_mr.iid = 3
    mock_mr.description = "This is a sufficiently long description for testing."
    mock_gl_client.get_merge_requests.return_value = [mock_mr]

    await gitlab_mr_description_length_warning_task()

    mock_mr.notes.create.assert_not_called()
