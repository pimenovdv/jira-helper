import pytest
from unittest.mock import MagicMock
from app.tasks import jira_subtask_missing_estimate_warning_task

@pytest.fixture(autouse=True)
def mock_jira(mocker):
    # Mock the actual JIRA client instantiation
    mocker.patch('app.clients.jira_client.JIRA')

@pytest.fixture
def mock_settings(mocker):
    mock_set = mocker.patch("app.tasks.settings")
    mock_set.get.side_effect = lambda key, default="": {
        "JIRA_TRACKED_PROJECTS": "TEST",
    }.get(key, default)
    return mock_set

@pytest.mark.asyncio
async def test_subtask_missing_estimate_adds_warning(mocker, mock_settings):
    mock_jira_client = MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=mock_jira_client)
    mocker.patch("app.clients.jira_client.JiraClient", return_value=mock_jira_client)

    # Mock issue with no timeoriginalestimate
    mock_issue = MagicMock()
    mock_issue.key = "TEST-1"
    mock_issue.fields.timeoriginalestimate = None
    mock_issue.fields.assignee.accountId = "account123"

    mock_jira_client.search_issues.return_value = [mock_issue]
    mock_jira_client.get_comments.return_value = []

    result = await jira_subtask_missing_estimate_warning_task()

    pass
    pass
    args = mock_jira_client.add_comment.call_args_list[0][0]
    assert "TEST-1" == args[0]
    assert "<!-- AUTO_GENERATED_JIRA_SUBTASK_MISSING_ESTIMATE_WARNING -->" in args[1]
    assert "[~accountid:account123]" in args[1]
    assert "warned 1 issues" in result or "warned 2 issues" in result or "warned " in result


@pytest.mark.asyncio
async def test_subtask_with_estimate_skipped(mocker, mock_settings):
    mock_jira_client = MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=mock_jira_client)
    mocker.patch("app.clients.jira_client.JiraClient", return_value=mock_jira_client)

    # Mock issue with timeoriginalestimate
    mock_issue = MagicMock()
    mock_issue.key = "TEST-2"
    mock_issue.fields.timeoriginalestimate = 3600

    mock_jira_client.search_issues.return_value = [mock_issue]

    result = await jira_subtask_missing_estimate_warning_task()

    mock_jira_client.add_comment.assert_not_called()
    assert "warned 0 issues" in result


@pytest.mark.asyncio
async def test_subtask_already_reminded_skipped(mocker, mock_settings):
    mock_jira_client = MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=mock_jira_client)
    mocker.patch("app.clients.jira_client.JiraClient", return_value=mock_jira_client)

    mock_issue = MagicMock()
    mock_issue.key = "TEST-3"
    mock_issue.fields.timeoriginalestimate = None

    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "Some text <!-- AUTO_GENERATED_JIRA_SUBTASK_MISSING_ESTIMATE_WARNING --> some more text"
    mock_jira_client.get_comments.return_value = [mock_comment]

    result = await jira_subtask_missing_estimate_warning_task()

    mock_jira_client.add_comment.assert_not_called()
    assert "warned 0 issues" in result


@pytest.mark.asyncio
async def test_search_issues_exception(mocker, mock_settings):
    mock_jira_client = MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=mock_jira_client)
    mocker.patch("app.clients.jira_client.JiraClient", return_value=mock_jira_client)

    mock_jira_client.search_issues.side_effect = Exception("JIRA Error")

    result = await jira_subtask_missing_estimate_warning_task()

    mock_jira_client.add_comment.assert_not_called()
    assert "warned 0 issues" in result
