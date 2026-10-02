import pytest
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_jira_stale_assigned_task_warning_task_adds_comment(mocker):
    from app.tasks import jira_stale_assigned_task_warning_task

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default="": "test_key" if k == "OPENAI_API_KEY" else ("PROJ1" if k == "JIRA_TRACKED_PROJECTS" else default)
    mocker.patch('app.tasks.settings', mock_settings)

    mock_jira_cls = mocker.patch('app.tasks.JiraClient')
    mock_jira = mock_jira_cls.return_value

    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.assignee.displayName = "Test User"
    mock_jira.search_issues.return_value = [mock_issue]

    mock_jira.get_comments.return_value = []

    mock_llm_cls = mocker.patch('app.tasks.ChatOpenAI')
    mock_llm = mock_llm_cls.return_value

    mock_response = MagicMock()
    mock_response.content = "Please provide an update."
    mock_llm.ainvoke = mocker.AsyncMock(return_value=mock_response)

    res = await jira_stale_assigned_task_warning_task()

    assert res == "Jira stale assigned task warning task completed"

    expected_jql = 'project = "PROJ1" AND assignee IS NOT EMPTY AND statusCategory != Done AND updated <= -7d'
    mock_jira.search_issues.assert_called_once_with(expected_jql)
    mock_jira.get_comments.assert_called_once_with("PROJ1-123")
    mock_llm.ainvoke.assert_awaited_once()
    mock_jira.add_comment.assert_called_once_with("PROJ1-123", "Please provide an update.")

@pytest.mark.asyncio
async def test_jira_stale_assigned_task_warning_task_already_reminded(mocker):
    from app.tasks import jira_stale_assigned_task_warning_task

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default="": "test_key" if k == "OPENAI_API_KEY" else ("PROJ1" if k == "JIRA_TRACKED_PROJECTS" else default)
    mocker.patch('app.tasks.settings', mock_settings)

    mock_jira_cls = mocker.patch('app.tasks.JiraClient')
    mock_jira = mock_jira_cls.return_value

    mock_issue = MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.assignee.displayName = "Test User"
    mock_jira.search_issues.return_value = [mock_issue]

    mock_comment = MagicMock()
    mock_comment.body = "<!-- AUTO_GENERATED_JIRA_STALE_ASSIGNED_TASK_WARNING --> already warned"
    mock_jira.get_comments.return_value = [mock_comment]

    mock_llm_cls = mocker.patch('app.tasks.ChatOpenAI')
    mock_llm = mock_llm_cls.return_value

    res = await jira_stale_assigned_task_warning_task()

    assert res == "Jira stale assigned task warning task completed"

    mock_jira.get_comments.assert_called_once_with("PROJ1-123")
    mock_llm.ainvoke.assert_not_called()
    mock_jira.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_stale_assigned_task_warning_task_no_api_key(mocker):
    from app.tasks import jira_stale_assigned_task_warning_task

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default="": "" if k == "OPENAI_API_KEY" else default
    mocker.patch('app.tasks.settings', mock_settings)

    res = await jira_stale_assigned_task_warning_task()

    assert res == "Jira stale assigned task warning task skipped (no OpenAI API key)"
