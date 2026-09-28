import pytest
from unittest.mock import MagicMock
from app.tasks import jira_unestimated_bug_warning_task

@pytest.fixture(autouse=True)
def mock_jira_lib(mocker):
    return mocker.patch("app.clients.jira_client.JIRA")

@pytest.fixture
def mock_jira_client(mocker):
    mock_module = mocker.patch("app.tasks.JiraClient")
    mock_instance = mock_module.return_value
    mocker.patch("app.clients.jira_client.JiraClient", return_value=mock_instance)
    return mock_instance

@pytest.fixture
def mock_settings(mocker):
    mock_s = MagicMock()
    mock_s.get.side_effect = lambda k, default="": {
        "JIRA_TRACKED_PROJECTS": "TESTPROJ",
        "JIRA_STORY_POINTS_FIELD": "customfield_10016"
    }.get(k, default)
    mocker.patch("app.tasks.settings", mock_s)
    mocker.patch("app.clients.settings", mock_s)
    mocker.patch("app.clients.jira_client.settings", mock_s)
    return mock_s

@pytest.mark.asyncio
async def test_no_issues(mock_jira_client, mock_settings):
    mock_jira_client.search_issues.return_value = []

    result = await jira_unestimated_bug_warning_task()

    assert "warned 0 issues" in result
    mock_jira_client.search_issues.assert_called_once_with('project = "TESTPROJ" AND issuetype = "Bug" AND sprint in openSprints()')
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_issue_already_warned(mock_jira_client, mock_settings):
    issue = MagicMock()
    issue.key = "TASK-1"
    issue.fields = MagicMock()
    issue.fields.customfield_10016 = None
    issue.fields.timeoriginalestimate = None

    comment = MagicMock()
    comment.body = "Warning <!-- AUTO_GENERATED_UNESTIMATED_BUG_WARNING -->"

    mock_jira_client.search_issues.return_value = [issue]
    mock_jira_client.get_comments.return_value = [comment]

    result = await jira_unestimated_bug_warning_task()

    assert "warned 0 issues" in result
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_issue_not_warned_adds_comment(mock_jira_client, mock_settings):
    issue = MagicMock()
    issue.key = "TASK-2"
    issue.fields = MagicMock()
    issue.fields.customfield_10016 = None
    issue.fields.timeoriginalestimate = None
    issue.fields.assignee = MagicMock()
    issue.fields.assignee.accountId = "12345"

    comment = MagicMock()
    comment.body = "Some regular comment"

    mock_jira_client.search_issues.return_value = [issue]
    mock_jira_client.get_comments.return_value = [comment]

    result = await jira_unestimated_bug_warning_task()

    assert "warned 1 issues" in result
    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "TASK-2"
    assert "<!-- AUTO_GENERATED_UNESTIMATED_BUG_WARNING -->" in args[1]
    assert "[~accountid:12345]" in args[1]

@pytest.mark.asyncio
async def test_issue_has_estimation(mock_jira_client, mock_settings):
    issue = MagicMock()
    issue.key = "TASK-3"
    issue.fields = MagicMock()
    issue.fields.customfield_10016 = 3  # has story points
    issue.fields.timeoriginalestimate = None

    mock_jira_client.search_issues.return_value = [issue]
    mock_jira_client.get_comments.return_value = []

    result = await jira_unestimated_bug_warning_task()

    assert "warned 0 issues" in result
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_issue_has_time_estimation(mock_jira_client, mock_settings):
    issue = MagicMock()
    issue.key = "TASK-4"
    issue.fields = MagicMock()
    issue.fields.customfield_10016 = None
    issue.fields.timeoriginalestimate = 3600  # has time original estimate

    mock_jira_client.search_issues.return_value = [issue]
    mock_jira_client.get_comments.return_value = []

    result = await jira_unestimated_bug_warning_task()

    assert "warned 0 issues" in result
    mock_jira_client.add_comment.assert_not_called()
