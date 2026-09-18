import pytest
from unittest.mock import MagicMock
from app.tasks import jira_unassigned_epic_warning_task

@pytest.fixture(autouse=True)
def mock_jira_client_init(mocker):
    mocker.patch('app.clients.jira_client.JIRA')

@pytest.fixture
def mock_jira_client(mocker):
    mock_jira = MagicMock()
    # Patch the JiraClient class directly in its source module because it's imported locally
    mocker.patch('app.clients.jira_client.JiraClient', return_value=mock_jira)
    return mock_jira

@pytest.mark.asyncio
async def test_unassigned_epic_warning_added(mock_jira_client):
    mock_issue = MagicMock()
    mock_issue.key = "TEST-1"
    mock_issue.fields.assignee = None

    mock_jira_client.search_issues.return_value = [mock_issue]
    mock_jira_client.get_comments.return_value = []

    await jira_unassigned_epic_warning_task()

    mock_jira_client.search_issues.assert_called_once_with("resolution = Unresolved AND issuetype = Epic")
    mock_jira_client.get_comments.assert_called_once_with("TEST-1")
    mock_jira_client.add_comment.assert_called_once()
    assert "<!-- AUTO_GENERATED_UNASSIGNED_EPIC_WARNING -->" in mock_jira_client.add_comment.call_args[0][1]

@pytest.mark.asyncio
async def test_unassigned_epic_warning_skipped_when_assigned(mock_jira_client):
    mock_issue = MagicMock()
    mock_issue.key = "TEST-2"
    mock_issue.fields.assignee = MagicMock()

    mock_jira_client.search_issues.return_value = [mock_issue]

    await jira_unassigned_epic_warning_task()

    mock_jira_client.search_issues.assert_called_once_with("resolution = Unresolved AND issuetype = Epic")
    mock_jira_client.get_comments.assert_not_called()
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_unassigned_epic_warning_skipped_when_already_warned(mock_jira_client):
    mock_issue = MagicMock()
    mock_issue.key = "TEST-3"
    mock_issue.fields.assignee = None

    mock_comment = MagicMock()
    mock_comment.body = "Some text <!-- AUTO_GENERATED_UNASSIGNED_EPIC_WARNING -->"

    mock_jira_client.search_issues.return_value = [mock_issue]
    mock_jira_client.get_comments.return_value = [mock_comment]

    await jira_unassigned_epic_warning_task()

    mock_jira_client.search_issues.assert_called_once_with("resolution = Unresolved AND issuetype = Epic")
    mock_jira_client.get_comments.assert_called_once_with("TEST-3")
    mock_jira_client.add_comment.assert_not_called()
