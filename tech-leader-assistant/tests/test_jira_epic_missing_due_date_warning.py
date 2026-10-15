import pytest
from unittest.mock import MagicMock, call

@pytest.mark.asyncio
async def test_jira_epic_missing_due_date_warning_task_warns(mocker):
    from app.tasks import jira_epic_missing_due_date_warning_task

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, d="": "TEST-PROJ" if k == "JIRA_PROJECT_KEY" else d
    mocker.patch("app.tasks.settings", mock_settings)
    mocker.patch("app.clients.settings", mock_settings)

    mock_jira_cls = mocker.patch("app.clients.jira_client.JiraClient")
    mock_jira = mock_jira_cls.return_value

    class MockComment:
        def __init__(self, body):
            self.body = body

    class MockAssignee:
        def __init__(self, display_name, account_id):
            self.displayName = display_name
            self.accountId = account_id

    class MockFieldsNoDueDate:
        def __init__(self):
            self.duedate = None
            self.assignee = MockAssignee("Test User", "test_acc_id")

    class MockFieldsWithDueDate:
        def __init__(self):
            self.duedate = "2024-12-31"
            self.assignee = MockAssignee("Test User", "test_acc_id")

    class MockIssue:
        def __init__(self, key, fields):
            self.key = key
            self.fields = fields

    mock_issue_no_due_date = MockIssue(key="TEST-1", fields=MockFieldsNoDueDate())
    mock_issue_with_due_date = MockIssue(key="TEST-2", fields=MockFieldsWithDueDate())

    mock_jira.search_issues.return_value = [mock_issue_no_due_date, mock_issue_with_due_date]
    mock_jira.get_comments.return_value = [MockComment(body="Some other comment")]
    mock_jira.add_comment.return_value = True

    res = await jira_epic_missing_due_date_warning_task()

    assert res == "Jira Epic missing due date warning task completed: warned 1 Epics."
    mock_jira.search_issues.assert_called_once_with('project = TEST-PROJ AND issuetype = Epic AND statusCategory != Done')
    mock_jira.add_comment.assert_called_once()
    args, _ = mock_jira.add_comment.call_args
    assert args[0] == "TEST-1"
    assert "<!-- AUTO_GENERATED_MISSING_DUE_DATE_WARNING -->" in args[1]
    assert "[~test_acc_id]" in args[1]


@pytest.mark.asyncio
async def test_jira_epic_missing_due_date_warning_task_already_warned(mocker):
    from app.tasks import jira_epic_missing_due_date_warning_task

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, d="": "TEST-PROJ" if k == "JIRA_PROJECT_KEY" else d
    mocker.patch("app.tasks.settings", mock_settings)
    mocker.patch("app.clients.settings", mock_settings)

    mock_jira_cls = mocker.patch("app.clients.jira_client.JiraClient")
    mock_jira = mock_jira_cls.return_value

    class MockComment:
        def __init__(self, body):
            self.body = body

    class MockAssignee:
        def __init__(self, display_name, account_id):
            self.displayName = display_name
            self.accountId = account_id

    class MockFieldsNoDueDate:
        def __init__(self):
            self.duedate = None
            self.assignee = MockAssignee("Test User", "test_acc_id")

    class MockIssue:
        def __init__(self, key, fields):
            self.key = key
            self.fields = fields

    mock_issue_no_due_date = MockIssue(key="TEST-1", fields=MockFieldsNoDueDate())

    mock_jira.search_issues.return_value = [mock_issue_no_due_date]
    mock_jira.get_comments.return_value = [MockComment(body="<!-- AUTO_GENERATED_MISSING_DUE_DATE_WARNING -->")]

    res = await jira_epic_missing_due_date_warning_task()

    assert res == "Jira Epic missing due date warning task completed: warned 0 Epics."
    mock_jira.add_comment.assert_not_called()
