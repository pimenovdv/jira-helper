import pytest
from app.tasks import jira_task_missing_estimate_warning_task

class MockIssue:
    def __init__(self, key, fields_dict):
        self.key = key
        class Fields:
            pass
        self.fields = Fields()
        for k, v in fields_dict.items():
            setattr(self.fields, k, v)

class MockComment:
    def __init__(self, body):
        self.body = body

@pytest.mark.asyncio
async def test_jira_task_missing_estimate_warning_task(mocker):
    # Mock settings
    mock_settings = mocker.patch("app.clients.settings")
    mock_settings.get.return_value = "PROJ1"

    # Mock JiraClient
    mock_jira_client_class = mocker.patch("app.clients.jira_client.JiraClient")
    mock_jira_client = mock_jira_client_class.return_value

    # Issue 1: Missing estimate, no previous warning
    issue1 = MockIssue("PROJ1-1", {"issuetype": "Task", "timeoriginalestimate": None})

    # Issue 2: Has estimate, shouldn't warn
    issue2 = MockIssue("PROJ1-2", {"issuetype": "Task", "timeoriginalestimate": 3600})

    # Issue 3: Missing estimate but already warned
    issue3 = MockIssue("PROJ1-3", {"issuetype": "Task", "timeoriginalestimate": None})

    mock_jira_client.search_issues.return_value = [issue1, issue2, issue3]

    def mock_get_comments(issue_key):
        if issue_key == "PROJ1-3":
            return [MockComment("<!-- AUTO_GENERATED_TASK_MISSING_ESTIMATE_WARNING -->\nWarning message")]
        return []

    mock_jira_client.get_comments.side_effect = mock_get_comments

    await jira_task_missing_estimate_warning_task()

    mock_jira_client.search_issues.assert_called_once_with(
        'project = "PROJ1" AND issuetype = "Task" AND statusCategory != Done'
    )

    # Check that add_comment was called only for issue1
    assert mock_jira_client.add_comment.call_count == 1
    call_args = mock_jira_client.add_comment.call_args[0]
    assert call_args[0] == "PROJ1-1"
    assert "<!-- AUTO_GENERATED_TASK_MISSING_ESTIMATE_WARNING -->" in call_args[1]
    assert "missing an original estimate" in call_args[1]
