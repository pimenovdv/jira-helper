import pytest
from unittest.mock import MagicMock

from app.tasks import jira_epic_missing_priority_warning_task


@pytest.fixture(autouse=True)
def mock_jira_init(mocker):
    return mocker.patch("app.clients.jira_client.JIRA")


@pytest.fixture
def mock_jira_client(mocker):
    return mocker.patch("app.clients.jira_client.JiraClient")


@pytest.fixture
def mock_settings(mocker):
    mock_set = mocker.patch("app.clients.settings")
    mock_set.get.return_value = "TESTPROJ"
    return mock_set


@pytest.mark.asyncio
async def test_jira_epic_missing_priority_warning_task_no_priority_no_marker(
    mock_jira_client, mock_settings
):
    jira_instance = mock_jira_client.return_value
    mock_issue = MagicMock()
    mock_issue.key = "TEST-1"
    mock_issue.fields.priority = None

    jira_instance.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "Some comment"
    jira_instance.get_comments.return_value = [mock_comment]
    mock_settings.get.return_value = "TESTPROJ"

    result = await jira_epic_missing_priority_warning_task()

    assert "Warned 1 epics" in result
    jira_instance.add_comment.assert_called_once()
    args, _ = jira_instance.add_comment.call_args
    assert args[0] == "TEST-1"
    assert "<!-- AUTO_GENERATED_EPIC_MISSING_PRIORITY_WARNING -->" in args[1]


@pytest.mark.asyncio
async def test_jira_epic_missing_priority_warning_task_no_priority_with_marker(
    mock_jira_client, mock_settings
):
    jira_instance = mock_jira_client.return_value
    mock_issue = MagicMock()
    mock_issue.key = "TEST-1"
    mock_issue.fields.priority = None

    jira_instance.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "<!-- AUTO_GENERATED_EPIC_MISSING_PRIORITY_WARNING -->"
    jira_instance.get_comments.return_value = [mock_comment]
    mock_settings.get.return_value = "TESTPROJ"

    result = await jira_epic_missing_priority_warning_task()

    assert "Warned 0 epics" in result
    jira_instance.add_comment.assert_not_called()


@pytest.mark.asyncio
async def test_jira_epic_missing_priority_warning_task_with_priority(
    mock_jira_client, mock_settings
):
    jira_instance = mock_jira_client.return_value
    mock_issue = MagicMock()
    mock_issue.key = "TEST-1"
    mock_issue.fields.priority = "High"

    jira_instance.search_issues.return_value = [mock_issue]
    mock_settings.get.return_value = "TESTPROJ"

    result = await jira_epic_missing_priority_warning_task()

    assert "Warned 0 epics" in result
    jira_instance.add_comment.assert_not_called()


@pytest.mark.asyncio
async def test_jira_epic_missing_priority_warning_task_exception(
    mock_jira_client, mock_settings
):
    jira_instance = mock_jira_client.return_value
    jira_instance.search_issues.side_effect = Exception("API error")
    mock_settings.get.return_value = "TESTPROJ"

    result = await jira_epic_missing_priority_warning_task()

    assert "Warned 0 epics" in result
