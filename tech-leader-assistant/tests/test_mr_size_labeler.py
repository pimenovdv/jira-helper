import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_size_labeler_task
from app.clients import settings

@pytest.fixture(autouse=True)
def setup_settings():
    original_projects = settings.get("GITLAB_TRACKED_PROJECTS")
    settings.set("GITLAB_TRACKED_PROJECTS", "project_1")
    yield
    settings.set("GITLAB_TRACKED_PROJECTS", original_projects)

@pytest.mark.asyncio
async def test_gitlab_mr_size_labeler_task_skips_existing(mocker):
    mock_client_instance = MagicMock()
    # Mocking GitLabClient since it is instantiated in the function.
    # Wait, in the task it's: gitlab_client = GitLabClient()
    # But wait, GitLabClient is NOT locally imported? Yes it is globally imported in tasks.py!
    mocker.patch("app.tasks.GitLabClient", return_value=mock_client_instance)

    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.labels = ["bug", "size: S"]

    mock_client_instance.get_project_merge_requests.return_value = [mock_mr]

    await gitlab_mr_size_labeler_task()

    mock_client_instance.get_merge_request_changes.assert_not_called()
    mock_client_instance.update_mr_labels.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("diff_text, expected_size", [
    ("+++ a\n--- b\n+ line 1\n- line 2\n+ line 3", "XS"),
    ("+++ a\n" + "+ line\n" * 15, "S"),
    ("+++ a\n" + "+ line\n" * 100, "M"),
    ("+++ a\n" + "+ line\n" * 500, "L"),
    ("+++ a\n" + "+ line\n" * 1200, "XL"),
])
async def test_gitlab_mr_size_labeler_task_assigns_size(mocker, diff_text, expected_size):
    mock_client_instance = MagicMock()
    mocker.patch("app.tasks.GitLabClient", return_value=mock_client_instance)

    mock_mr = MagicMock()
    mock_mr.iid = 2
    mock_mr.labels = ["feature"]

    mock_client_instance.get_project_merge_requests.return_value = [mock_mr]

    mock_changes = {
        "changes": [
            {"diff": diff_text}
        ]
    }
    mock_client_instance.get_merge_request_changes.return_value = mock_changes

    await gitlab_mr_size_labeler_task()

    expected_labels = ["feature", f"size: {expected_size}"]

    mock_client_instance.update_mr_labels.assert_called_once_with("project_1", 2, expected_labels)


@pytest.mark.asyncio
async def test_gitlab_mr_size_labeler_task_handles_exceptions(mocker, caplog):
    mock_client_instance = MagicMock()
    mocker.patch("app.tasks.GitLabClient", return_value=mock_client_instance)

    mock_client_instance.get_project_merge_requests.side_effect = Exception("API error")

    await gitlab_mr_size_labeler_task()

    assert "Error processing MR size labeler for project project_1" in caplog.text
