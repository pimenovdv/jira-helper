import pytest
from unittest.mock import MagicMock
from app.tasks import jira_epic_without_child_issues_warning_task

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.tasks.settings")
    # Store original values
    original_get = mock.get

    class MockSettings:
        def __init__(self):
            self._project_key = "TEST-PROJ"

        def get(self, key, default=None):
            if key == "JIRA_PROJECT_KEY":
                return self._project_key
            return None

    mock_inst = MockSettings()
    mock.get.side_effect = mock_inst.get

    mock_client = mocker.patch("app.clients.settings")
    mock_client.get.side_effect = mock_inst.get

    return mock_inst

@pytest.fixture(autouse=True)
def mock_jira(mocker):
    return mocker.patch("app.clients.jira_client.JIRA")

@pytest.fixture
def mock_jira_client(mocker):
    # This specifically patches the global JiraClient imported at the top of app/tasks.py
    mock = mocker.patch("app.tasks.JiraClient")
    client_instance = MagicMock()
    mock.return_value = client_instance
    return client_instance

@pytest.mark.asyncio
async def test_jira_epic_without_child_issues_warning_task_no_project(mock_settings, mock_jira_client):
    mock_settings._project_key = None
    res = await jira_epic_without_child_issues_warning_task()
    assert "aborted" in res
    mock_jira_client.search_issues.assert_not_called()

@pytest.mark.asyncio
async def test_jira_epic_without_child_issues_warning_task_has_children(mock_settings, mock_jira_client):
    epic = MagicMock()
    epic.key = "TEST-1"

    child = MagicMock()

    def mock_search_issues(jql):
        if "issuetype = Epic" in jql:
            return [epic]
        else:
            return [child]

    mock_jira_client.search_issues.side_effect = mock_search_issues

    res = await jira_epic_without_child_issues_warning_task()

    assert "warned 0 Epics" in res
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_epic_without_child_issues_warning_task_already_warned(mock_settings, mock_jira_client):
    epic = MagicMock()
    epic.key = "TEST-1"

    comment = MagicMock()
    comment.body = "<!-- AUTO_GENERATED_EPIC_NO_CHILD_ISSUES_WARNING -->\nblabla"

    def mock_search_issues(jql):
        if "issuetype = Epic" in jql:
            return [epic]
        else:
            return []

    mock_jira_client.search_issues.side_effect = mock_search_issues
    mock_jira_client.get_comments.return_value = [comment]

    res = await jira_epic_without_child_issues_warning_task()

    assert "warned 0 Epics" in res
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_epic_without_child_issues_warning_task_success(mock_settings, mock_jira_client):
    epic = MagicMock()
    epic.key = "TEST-1"
    epic.fields.assignee.displayName = "Ivan"
    epic.fields.assignee.accountId = "12345"

    # Needs a custom side effect function for search_issues
    # When jql is for Epics, return [epic]
    # When jql is for child issues, return []
    def mock_search_issues(jql):
        if "issuetype = Epic" in jql:
            return [epic]
        else:
            return []

    mock_jira_client.search_issues.side_effect = mock_search_issues
    mock_jira_client.get_comments.return_value = []

    mock_jira_client.add_comment.return_value = True

    res = await jira_epic_without_child_issues_warning_task()

    assert "warned 1 Epics" in res
    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "TEST-1"
    assert "<!-- AUTO_GENERATED_EPIC_NO_CHILD_ISSUES_WARNING -->" in args[1]
    assert "[~12345]" in args[1]
