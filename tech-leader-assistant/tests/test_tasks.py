import app.tasks
import pytest

@pytest.fixture(autouse=True)
def mock_astext(monkeypatch):
    from sqlalchemy.sql.elements import BinaryExpression
    monkeypatch.setattr(BinaryExpression, "astext", property(lambda self: self), raising=False)

from unittest.mock import MagicMock
from app.tasks import jira_sync_task

@pytest.mark.asyncio
async def test_jira_sync_task(mocker):
    # Mock settings
    def mock_settings_get(key, default=""):
        if key == "GITLAB_TRACKED_PROJECTS":
            return "1, 2"
        elif key == "JIRA_TRACKED_PROJECTS":
            return "PROJ1"
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)


    # Mock GitLabClient
    mock_gitlab_client_cls = mocker.patch('app.tasks.GitLabClient')
    mock_gitlab = mock_gitlab_client_cls.return_value

    mock_branch_1 = MagicMock()
    mock_branch_1.name = "feature/PROJ1-123-new-feature"
    mock_branch_2 = MagicMock()
    mock_branch_2.name = "release/v1.0.0"

    mock_branch_3 = MagicMock()
    mock_branch_3.name = "fix/PROJ1-456-bug"

    # Project 1 branches
    # Project 2 branches
    mock_gitlab.get_project_branches.side_effect = lambda pid: [mock_branch_1, mock_branch_2] if pid == "1" else [mock_branch_3]

    # Mock JiraClient
    mock_jira_client_cls = mocker.patch('app.tasks.JiraClient')
    mock_jira = mock_jira_client_cls.return_value

    mock_issue_1 = MagicMock()
    mock_issue_1.key = "PROJ1-123"
    mock_issue_1.fields.summary = "New Feature"
    mock_version = MagicMock()
    mock_version.name = "v1.0.0"
    mock_issue_1.fields.fixVersions = [mock_version]

    mock_issue_2 = MagicMock()
    mock_issue_2.key = "PROJ1-456"
    mock_issue_2.fields.summary = "Bug Fix"

    mock_issue_3 = MagicMock()
    mock_issue_3.key = "PROJ1-789"
    mock_issue_3.fields.summary = "Unrelated"

    mock_jira.search_issues.return_value = [mock_issue_1, mock_issue_2, mock_issue_3]

    mock_release_1 = MagicMock()
    mock_release_1.name = "v1.0.0"
    mock_release_1.projectId = "10000"
    mock_jira.get_project_versions.return_value = [mock_release_1]

    # Mock AsyncSessionLocal and database operations
    mock_session = mocker.AsyncMock()
    mock_session.add = mocker.MagicMock()
    mock_session_cls = mocker.patch('app.tasks.AsyncSessionLocal')
    mock_session_cls.return_value.__aenter__.return_value = mock_session

    # Mock execute for checking existing events (assume none exist)
    mock_result = mocker.MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    # Run the task
    result = await jira_sync_task()
    assert result == "Jira sync task completed"

    # Verify cross-match logic by checking session.add calls
    # Should save: PROJ1-123 (proj 1), PROJ1-456 (proj 2), v1.0.0 (proj 1)
    # Total 3 add calls

    for call in mock_session.add.call_args_list:
        e = call.args[0]
        print(f"EVENT ADDED: {e.event_type} - {e.data}")
    assert mock_session.add.call_count == 4


    added_events = [call.args[0] for call in mock_session.add.call_args_list]

    # Check first task crossmatch
    task_1_event = next(e for e in added_events if e.event_type == "jira_task_crossmatch" and e.data["task_id"] == "PROJ1-123")
    assert task_1_event.data["matched_gitlab_projects"] == ["1"]

    # Check second task crossmatch
    task_2_event = next(e for e in added_events if e.event_type == "jira_task_crossmatch" and e.data["task_id"] == "PROJ1-456")
    assert task_2_event.data["matched_gitlab_projects"] == ["2"]

    # Check release crossmatch
    release_event = next(e for e in added_events if e.event_type == "jira_release_crossmatch" and e.data["release_name"] == "v1.0.0")
    assert release_event.data["matched_gitlab_projects"] == ["1"]

    mock_session.commit.assert_called_once()
