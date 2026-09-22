import pytest
from unittest.mock import MagicMock
from app.tasks import jira_bug_missing_attachment_warning_task
from app import tasks

@pytest.fixture
def mock_jira_client(mocker):
    # Because JiraClient is imported LOCALLY inside the function,
    # we cannot easily mock "app.tasks.JiraClient".
    # Instead, we mock the module it is imported FROM.
    mock_module = mocker.patch("app.clients.jira_client.JiraClient")
    mock_instance = mock_module.return_value
    return mock_instance

@pytest.mark.asyncio
async def test_no_unresolved_bugs(mock_jira_client):
    mock_jira_client.search_issues.return_value = []

    result = await jira_bug_missing_attachment_warning_task()

    assert result == "No unresolved bugs found"
    mock_jira_client.search_issues.assert_called_once_with("issuetype = Bug AND resolution = Unresolved")
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_has_attachment(mock_jira_client):
    issue = MagicMock()
    issue.key = "BUG-1"
    issue.fields = MagicMock()
    issue.fields.attachment = [MagicMock()]

    mock_jira_client.search_issues.return_value = [issue]

    result = await jira_bug_missing_attachment_warning_task()

    assert "warned 0 bugs" in result
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_no_attachment_but_already_warned(mock_jira_client):
    issue = MagicMock()
    issue.key = "BUG-2"
    issue.fields = MagicMock()
    del issue.fields.attachment

    comment = MagicMock()
    comment.body = "Some text <!-- AUTO_GENERATED_MISSING_ATTACHMENT_WARNING -->"

    mock_jira_client.search_issues.return_value = [issue]
    mock_jira_client.get_comments.return_value = [comment]

    result = await jira_bug_missing_attachment_warning_task()

    assert "warned 0 bugs" in result
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_no_attachment_adds_comment(mock_jira_client):
    issue = MagicMock()
    issue.key = "BUG-3"
    issue.fields = MagicMock()
    del issue.fields.attachment

    comment = MagicMock()
    comment.body = "Some other comment"

    mock_jira_client.search_issues.return_value = [issue]
    mock_jira_client.get_comments.return_value = [comment]

    result = await jira_bug_missing_attachment_warning_task()

    assert "warned 1 bugs" in result
    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "BUG-3"
    assert "<!-- AUTO_GENERATED_MISSING_ATTACHMENT_WARNING -->" in args[1]

@pytest.mark.asyncio
async def test_handles_exception_during_check(mock_jira_client):
    issue = MagicMock()
    issue.key = "BUG-4"
    issue.fields = MagicMock()
    del issue.fields.attachment

    mock_jira_client.search_issues.return_value = [issue]
    mock_jira_client.get_comments.side_effect = Exception("Test Error")

    result = await jira_bug_missing_attachment_warning_task()

    assert "warned 0 bugs" in result
    mock_jira_client.add_comment.assert_not_called()
