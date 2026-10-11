import pytest
from unittest.mock import MagicMock
from app.tasks import jira_bug_missing_components_warning_task

@pytest.fixture(autouse=True)
def mock_jira_client_init(mocker):
    mocker.patch('app.clients.jira_client.JIRA')

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.tasks.settings")
    mock.get.side_effect = lambda key, default="": {
        "JIRA_TRACKED_PROJECTS": "PROJ1",
    }.get(key, default)
    # Also patch clients settings
    mocker.patch("app.clients.jira_client.settings", mock)
    mocker.patch("app.clients.settings", mock)
    return mock

@pytest.fixture
def mock_jira_client_class(mocker):
    return mocker.patch("app.tasks.JiraClient")

@pytest.mark.asyncio
async def test_jira_bug_missing_components_warning_task_adds_comment(mocker, mock_settings, mock_jira_client_class):
    mock_jira_client_instance = mock_jira_client_class.return_value

    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields = MagicMock()
    mock_issue.fields.components = []

    mock_assignee = MagicMock()
    mock_assignee.accountId = "account-123"
    mock_issue.fields.assignee = mock_assignee

    mock_jira_client_instance.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "Some unrelated comment"
    mock_jira_client_instance.get_comments.return_value = [mock_comment]

    result = await jira_bug_missing_components_warning_task()

    mock_jira_client_instance.search_issues.assert_called_with('project = "PROJ1" AND issuetype = "Bug" AND statusCategory != "Done"')
    mock_jira_client_instance.get_comments.assert_called_once_with("PROJ1-123")
    mock_jira_client_instance.add_comment.assert_called_once()

    call_args = mock_jira_client_instance.add_comment.call_args[0]
    assert "PROJ1-123" in call_args[0]
    assert "<!-- AUTO_GENERATED_BUG_MISSING_COMPONENTS_WARNING -->" in call_args[1]
    assert "[~accountid:account-123]" in call_args[1]
    assert "у этого бага (Bug) не указан ни один компонент" in call_args[1]
    assert "warned 1 issues" in result


@pytest.mark.asyncio
async def test_jira_bug_missing_components_warning_task_skips_has_components(mocker, mock_settings, mock_jira_client_class):
    mock_jira_client_instance = mock_jira_client_class.return_value

    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields = MagicMock()
    mock_issue.fields.components = [{"name": "Backend"}]

    mock_jira_client_instance.search_issues.return_value = [mock_issue]

    result = await jira_bug_missing_components_warning_task()

    mock_jira_client_instance.get_comments.assert_not_called()
    mock_jira_client_instance.add_comment.assert_not_called()
    assert "warned 0 issues" in result


@pytest.mark.asyncio
async def test_jira_bug_missing_components_warning_task_skips_already_warned(mocker, mock_settings, mock_jira_client_class):
    mock_jira_client_instance = mock_jira_client_class.return_value

    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields = MagicMock()
    mock_issue.fields.components = []

    mock_jira_client_instance.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "<!-- AUTO_GENERATED_BUG_MISSING_COMPONENTS_WARNING -->"
    mock_jira_client_instance.get_comments.return_value = [mock_comment]

    result = await jira_bug_missing_components_warning_task()

    mock_jira_client_instance.get_comments.assert_called_once_with("PROJ1-123")
    mock_jira_client_instance.add_comment.assert_not_called()
    assert "warned 0 issues" in result
