import pytest
from unittest.mock import MagicMock
from app.tasks import jira_high_complexity_warning_task
from app import tasks

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch.object(tasks, "settings")
    mock.get.side_effect = lambda k, d="": "sk-test" if k == "OPENAI_API_KEY" else "PROJ" if k == "JIRA_TRACKED_PROJECTS" else "customfield_10016" if k == "JIRA_STORY_POINTS_FIELD" else d
    return mock

@pytest.fixture
def mock_jira_client(mocker):
    mock_cls = mocker.patch.object(tasks, "JiraClient")
    mock_instance = mock_cls.return_value
    return mock_instance

@pytest.fixture
def mock_llm(mocker):
    mock_cls = mocker.patch.object(tasks, "ChatOpenAI")
    mock_instance = mock_cls.return_value
    mock_instance.ainvoke = mocker.AsyncMock(return_value=MagicMock(content="Mock response"))
    return mock_instance

@pytest.mark.asyncio
async def test_jira_high_complexity_warning_task_no_api_key(mocker):
    mock = mocker.patch.object(tasks, "settings")
    mock.get.return_value = ""
    res = await jira_high_complexity_warning_task()
    assert "skipped" in res

@pytest.mark.asyncio
async def test_jira_high_complexity_warning_task_success(mock_settings, mock_jira_client, mock_llm, mocker):
    mock_jira_client.get_project_sprints.return_value = [{"id": 1, "state": "active"}]

    mock_issue = {
        "key": "PROJ-1",
        "fields": {
            "issuetype": {"name": "Task"},
            "customfield_10016": 13,
            "reporter": {"accountId": "user123"}
        }
    }
    mock_jira_client.get_sprint_issues.return_value = [mock_issue]

    mock_jira_client.get_issue_comments.return_value = []

    res = await jira_high_complexity_warning_task()

    mock_llm.ainvoke.assert_called_once()
    mock_jira_client.add_issue_comment.assert_called_once()
    args = mock_jira_client.add_issue_comment.call_args[0]
    assert args[0] == "PROJ-1"
    assert "AUTO_GENERATED_JIRA_HIGH_COMPLEXITY_WARNING" in args[1]
    assert "Mock response" in args[1]
    assert "completed" in res

@pytest.mark.asyncio
async def test_jira_high_complexity_warning_task_skip_epic(mock_settings, mock_jira_client, mock_llm, mocker):
    mock_jira_client.get_project_sprints.return_value = [{"id": 1, "state": "active"}]
    mock_issue = {
        "key": "PROJ-1",
        "fields": {
            "issuetype": {"name": "Epic"},
            "customfield_10016": 21,
            "reporter": {"accountId": "user123"}
        }
    }
    mock_jira_client.get_sprint_issues.return_value = [mock_issue]

    await jira_high_complexity_warning_task()
    mock_llm.ainvoke.assert_not_called()
    mock_jira_client.add_issue_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_high_complexity_warning_task_low_complexity(mock_settings, mock_jira_client, mock_llm, mocker):
    mock_jira_client.get_project_sprints.return_value = [{"id": 1, "state": "active"}]
    mock_issue = {
        "key": "PROJ-1",
        "fields": {
            "issuetype": {"name": "Task"},
            "customfield_10016": 5,
            "reporter": {"accountId": "user123"}
        }
    }
    mock_jira_client.get_sprint_issues.return_value = [mock_issue]

    await jira_high_complexity_warning_task()
    mock_llm.ainvoke.assert_not_called()
    mock_jira_client.add_issue_comment.assert_not_called()
