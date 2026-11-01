import pytest
from unittest.mock import MagicMock
from app.tasks import jira_epic_missing_priority_warning_task

@pytest.mark.asyncio
async def test_jira_epic_missing_priority_warning_task(mocker):
    mock_settings = MagicMock()
    mock_settings.get.return_value = "PROJ"
    mocker.patch("app.clients.settings", mock_settings)

    mock_jira = MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=mock_jira)

    mock_issue1 = MagicMock()
    mock_issue1.key = "PROJ-1"
    mock_issue1.fields.priority = None
    mock_issue1.fields.assignee = MagicMock()
    mock_issue1.fields.assignee.accountId = "user123"

    mock_issue2 = MagicMock()
    mock_issue2.key = "PROJ-2"
    mock_issue2.fields.priority = MagicMock()
    mock_issue2.fields.priority.name = "High"

    mock_jira.search_issues.return_value = [mock_issue1, mock_issue2]
    mock_jira.get_comments.return_value = []

    await jira_epic_missing_priority_warning_task()

    mock_jira.add_comment.assert_called_once()
    assert "PROJ-1" in mock_jira.add_comment.call_args[0][0]
    assert "AUTO_GENERATED_MISSING_EPIC_PRIORITY_WARNING" in mock_jira.add_comment.call_args[0][1]


@pytest.mark.asyncio
async def test_jira_epic_missing_priority_already_warned(mocker):
    mock_settings = MagicMock()
    mock_settings.get.return_value = "PROJ"
    mocker.patch("app.clients.settings", mock_settings)

    mock_jira = MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=mock_jira)

    mock_issue = MagicMock()
    mock_issue.key = "PROJ-1"
    mock_issue.fields.priority = None

    mock_jira.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "<!-- AUTO_GENERATED_MISSING_EPIC_PRIORITY_WARNING -->"
    mock_jira.get_comments.return_value = [mock_comment]

    await jira_epic_missing_priority_warning_task()

    mock_jira.add_comment.assert_not_called()
