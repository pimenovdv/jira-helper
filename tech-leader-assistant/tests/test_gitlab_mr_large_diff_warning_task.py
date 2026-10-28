import pytest
from unittest.mock import MagicMock

from app.tasks import gitlab_mr_large_diff_warning_task


@pytest.fixture(autouse=True)
def mock_gitlab_init(mocker):
    return mocker.patch("app.clients.gitlab_client.gitlab.Gitlab")


@pytest.fixture
def mock_gitlab_client(mocker):
    return mocker.patch("app.clients.gitlab_client.GitLabClient")


@pytest.fixture
def mock_settings(mocker):
    mock_set = mocker.patch("app.clients.settings")
    mock_set.get.return_value = "TESTPROJ"
    return mock_set


@pytest.mark.asyncio
async def test_gitlab_mr_large_diff_warning_task_large_diff_no_marker(
    mock_gitlab_client, mock_settings
):
    gl_client_instance = mock_gitlab_client.return_value
    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.iid = 1

    mock_mr_obj = MagicMock()
    mock_mr_obj.iid = 1
    diff_content = "+ line1\n" * 251 + "- line2\n" * 251
    mock_mr_obj.changes.return_value = {"changes": [{"diff": diff_content}]}

    mock_project.mergerequests.get.return_value = mock_mr_obj

    gl_client_instance.get_project_merge_requests.return_value = [mock_mr]
    gl_client_instance.get_project.return_value = mock_project

    mock_mr_obj.notes.list.return_value = []
    mock_settings.get.return_value = "TESTPROJ"

    result = await gitlab_mr_large_diff_warning_task()

    assert "warned 1 MRs" in result
    mock_mr_obj.notes.create.assert_called_once()
    args, kwargs = mock_mr_obj.notes.create.call_args
    assert "<!-- AUTO_GENERATED_GITLAB_MR_LARGE_DIFF_WARNING -->" in args[0]["body"]
    assert "502 lines" in args[0]["body"]


@pytest.mark.asyncio
async def test_gitlab_mr_large_diff_warning_task_large_diff_with_marker(
    mock_gitlab_client, mock_settings
):
    gl_client_instance = mock_gitlab_client.return_value
    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.iid = 1

    mock_mr_obj = MagicMock()
    mock_mr_obj.iid = 1
    diff_content = "+ line1\n" * 501
    mock_mr_obj.changes.return_value = {"changes": [{"diff": diff_content}]}

    mock_project.mergerequests.get.return_value = mock_mr_obj

    gl_client_instance.get_project_merge_requests.return_value = [mock_mr]
    gl_client_instance.get_project.return_value = mock_project

    mock_note = MagicMock()
    mock_note.body = "<!-- AUTO_GENERATED_GITLAB_MR_LARGE_DIFF_WARNING -->"
    mock_mr_obj.notes.list.return_value = [mock_note]
    mock_settings.get.return_value = "TESTPROJ"

    result = await gitlab_mr_large_diff_warning_task()

    assert "warned 0 MRs" in result
    mock_mr_obj.notes.create.assert_not_called()


@pytest.mark.asyncio
async def test_gitlab_mr_large_diff_warning_task_small_diff(
    mock_gitlab_client, mock_settings
):
    gl_client_instance = mock_gitlab_client.return_value
    mock_project = MagicMock()
    mock_mr = MagicMock()
    mock_mr.iid = 1

    mock_mr_obj = MagicMock()
    mock_mr_obj.iid = 1
    diff_content = "+ line1\n" * 10
    mock_mr_obj.changes.return_value = {"changes": [{"diff": diff_content}]}

    mock_project.mergerequests.get.return_value = mock_mr_obj

    gl_client_instance.get_project_merge_requests.return_value = [mock_mr]
    gl_client_instance.get_project.return_value = mock_project
    mock_settings.get.return_value = "TESTPROJ"

    result = await gitlab_mr_large_diff_warning_task()

    assert "warned 0 MRs" in result
    mock_mr_obj.notes.create.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_large_diff_warning_task_exception(
    mock_gitlab_client, mock_settings
):
    gl_client_instance = mock_gitlab_client.return_value
    gl_client_instance.get_project_merge_requests.side_effect = Exception("API error")
    mock_settings.get.return_value = "TESTPROJ"

    result = await gitlab_mr_large_diff_warning_task()

    assert "warned 0 MRs" in result
