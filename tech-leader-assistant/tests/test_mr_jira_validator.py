import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_jira_validator_task
from app.clients import settings
import logging

@pytest.fixture(autouse=True)
def setup_settings():
    original_projects = settings.get("GITLAB_TRACKED_PROJECTS", "")
    settings.set("GITLAB_TRACKED_PROJECTS", "project123")
    yield
    settings.set("GITLAB_TRACKED_PROJECTS", original_projects)

@pytest.fixture
def mock_gitlab_client(mocker):
    mock_client = MagicMock()
    mocker.patch("app.tasks.GitLabClient", return_value=mock_client)
    return mock_client

@pytest.mark.asyncio
async def test_gitlab_mr_jira_validator_missing_id(mock_gitlab_client):
    # Setup mock MR without Jira ID
    mock_mr = MagicMock()
    mock_mr.title = "Fix typo in documentation"
    mock_mr.iid = 1

    # Setup mock notes (no reminder yet)
    mock_note = MagicMock()
    mock_note.body = "Just a regular comment"
    mock_mr.notes.list.return_value = [mock_note]

    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr]

    result = await gitlab_mr_jira_validator_task()

    assert result == "MR Jira validator task completed"
    mock_gitlab_client.create_mr_note.assert_called_once()
    args, _ = mock_gitlab_client.create_mr_note.call_args
    assert args[0] == "project123"
    assert args[1] == 1
    assert "<!-- AUTO_GENERATED_MR_JIRA_VALIDATOR_REMINDER -->" in args[2]

@pytest.mark.asyncio
async def test_gitlab_mr_jira_validator_has_id(mock_gitlab_client):
    # Setup mock MR with Jira ID
    mock_mr = MagicMock()
    mock_mr.title = "PROJ-123: Add new feature"
    mock_mr.iid = 2

    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr]

    result = await gitlab_mr_jira_validator_task()

    assert result == "MR Jira validator task completed"
    mock_mr.notes.list.assert_not_called()
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_jira_validator_has_reminder(mock_gitlab_client):
    # Setup mock MR without Jira ID
    mock_mr = MagicMock()
    mock_mr.title = "Fix another typo"
    mock_mr.iid = 3

    # Setup mock notes with the reminder already present
    mock_note = MagicMock()
    mock_note.body = "Please add Jira task ID... <!-- AUTO_GENERATED_MR_JIRA_VALIDATOR_REMINDER -->"
    mock_mr.notes.list.return_value = [mock_note]

    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr]

    result = await gitlab_mr_jira_validator_task()

    assert result == "MR Jira validator task completed"
    mock_mr.notes.list.assert_called_once_with(all=True)
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_jira_validator_exception_handling(mock_gitlab_client, caplog):
    mock_gitlab_client.get_project_merge_requests.side_effect = Exception("GitLab API error")

    with caplog.at_level(logging.ERROR):
        result = await gitlab_mr_jira_validator_task()

    assert result == "MR Jira validator task completed"
    assert "Error processing MR Jira validator for project project123" in caplog.text
