import pytest
from unittest.mock import MagicMock
from app.tasks import jira_sprint_goal_missing_warning_task

@pytest.mark.asyncio
async def test_jira_sprint_goal_missing_warning_task(mocker):
    mock_settings = MagicMock()
    mock_settings.get.return_value = "PROJ"
    mocker.patch("app.clients.settings", mock_settings)

    mock_jira = MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=mock_jira)

    mock_issue1 = MagicMock()
    mock_issue1.key = "PROJ-1"
    mock_issue1.fields.assignee = MagicMock()
    mock_issue1.fields.assignee.accountId = "user123"

    mock_sprint = MagicMock()
    mock_sprint.id = 1
    mock_sprint.goal = ""
    mock_issue1.fields.customfield_10020 = [mock_sprint]

    mock_issue2 = MagicMock()
    mock_issue2.key = "PROJ-2"
    mock_issue2.fields.assignee = MagicMock()
    mock_issue2.fields.assignee.accountId = "user456"

    mock_sprint2 = MagicMock()
    mock_sprint2.id = 2
    mock_sprint2.goal = "To deliver the feature X"
    mock_issue2.fields.customfield_10020 = [mock_sprint2]

    mock_jira.search_issues.return_value = [mock_issue1, mock_issue2]
    mock_jira.get_comments.return_value = []

    await jira_sprint_goal_missing_warning_task()

    mock_jira.add_comment.assert_called_once_with(
        "PROJ-1",
        "<!-- AUTO_GENERATED_MISSING_SPRINT_GOAL_WARNING -->\nHi [~accountid:user123],\n\nThe current active sprint this issue belongs to appears to be missing a **Sprint Goal**.\nSprints without clear goals can suffer from scope creep. Please ensure the sprint goal is defined."
    )

@pytest.mark.asyncio
async def test_jira_sprint_goal_missing_already_warned(mocker):
    mock_settings = MagicMock()
    mock_settings.get.return_value = "PROJ"
    mocker.patch("app.clients.settings", mock_settings)

    mock_jira = MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=mock_jira)

    mock_issue1 = MagicMock()
    mock_issue1.key = "PROJ-1"

    mock_sprint = MagicMock()
    mock_sprint.id = 1
    mock_sprint.goal = ""
    mock_issue1.fields.customfield_10020 = [mock_sprint]

    mock_jira.search_issues.return_value = [mock_issue1]

    mock_comment = MagicMock()
    mock_comment.body = "<!-- AUTO_GENERATED_MISSING_SPRINT_GOAL_WARNING -->"
    mock_jira.get_comments.return_value = [mock_comment]

    await jira_sprint_goal_missing_warning_task()

    mock_jira.add_comment.assert_not_called()
