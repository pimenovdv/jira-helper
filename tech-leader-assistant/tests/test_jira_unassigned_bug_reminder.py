import pytest
from unittest.mock import MagicMock
from app.tasks import jira_unassigned_bug_reminder_task

@pytest.fixture
def mock_jira_client(mocker):
    client = MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=client)
    return client

@pytest.fixture
def mock_settings(mocker):
    mock = MagicMock()
    mock.get.side_effect = lambda key, default="": "PROJ1" if key == "JIRA_TRACKED_PROJECTS" else default
    mocker.patch("app.tasks.settings", mock)
    return mock

@pytest.mark.asyncio
async def test_unassigned_bug_reminded(mock_jira_client, mock_settings):
    issue1 = MagicMock()
    issue1.key = "PROJ1-123"
    issue1.fields.assignee = None

    mock_jira_client.search_issues.return_value = [issue1]
    mock_jira_client.get_comments.return_value = []

    await jira_unassigned_bug_reminder_task()

    mock_jira_client.search_issues.assert_called_once_with(
        'project = "PROJ1" AND issuetype = "Bug" AND statusCategory != "Done" AND created <= -2d'
    )
    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "PROJ1-123"
    assert "AUTO_GENERATED_UNASSIGNED_BUG_REMINDER" in args[1]


@pytest.mark.asyncio
async def test_assigned_bug_ignored(mock_jira_client, mock_settings):
    issue1 = MagicMock()
    issue1.key = "PROJ1-124"
    issue1.fields.assignee = MagicMock()
    issue1.fields.assignee.name = "john.doe"

    mock_jira_client.search_issues.return_value = [issue1]

    await jira_unassigned_bug_reminder_task()

    mock_jira_client.add_comment.assert_not_called()


@pytest.mark.asyncio
async def test_already_reminded_bug_ignored(mock_jira_client, mock_settings):
    issue1 = MagicMock()
    issue1.key = "PROJ1-125"
    issue1.fields.assignee = None

    comment = MagicMock()
    comment.body = "Reminder: This bug is unassigned... <!-- AUTO_GENERATED_UNASSIGNED_BUG_REMINDER -->"

    mock_jira_client.search_issues.return_value = [issue1]
    mock_jira_client.get_comments.return_value = [comment]

    await jira_unassigned_bug_reminder_task()

    mock_jira_client.add_comment.assert_not_called()
