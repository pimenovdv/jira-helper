import pytest
from unittest.mock import MagicMock, AsyncMock
from app.tasks import jira_closed_missing_resolution_task

@pytest.fixture
def mock_settings(mocker):
    mock = MagicMock()
    mock.get.side_effect = lambda k, d="": "TEST_KEY" if k == "OPENAI_API_KEY" else "PROJ1" if k == "JIRA_TRACKED_PROJECTS" else d
    mocker.patch("app.tasks.settings", mock)
    return mock

@pytest.fixture
def mock_jira_client(mocker):
    mock = MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=mock)
    return mock

@pytest.fixture
def mock_llm(mocker):
    mock_response = MagicMock()
    mock_response.content = "Please set a resolution."
    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value=mock_response)
    mocker.patch("app.tasks.ChatOpenAI", return_value=mock)
    return mock

@pytest.mark.asyncio
async def test_missing_resolution_reminder(mock_settings, mock_jira_client, mock_llm):
    # Setup mock issue
    issue1 = MagicMock()
    issue1.key = "PROJ1-1"
    issue1.fields.resolution = None
    issue1.fields.assignee.accountId = "account123"

    mock_jira_client.search_issues.return_value = [issue1]
    mock_jira_client.get_comments.return_value = []

    res = await jira_closed_missing_resolution_task()

    assert res == "Jira closed missing resolution reminder task completed."
    mock_jira_client.search_issues.assert_called_once_with('project = "PROJ1" AND statusCategory = Done AND resolution = EMPTY')
    mock_llm.ainvoke.assert_awaited_once()
    mock_jira_client.add_comment.assert_called_once()
    args, _ = mock_jira_client.add_comment.call_args
    assert args[0] == "PROJ1-1"
    assert "Please set a resolution." in args[1]
    assert "<!-- AUTO_GENERATED_MISSING_RESOLUTION -->" in args[1]

@pytest.mark.asyncio
async def test_missing_resolution_already_commented(mock_settings, mock_jira_client, mock_llm):
    issue1 = MagicMock()
    issue1.key = "PROJ1-2"
    issue1.fields.resolution = None

    comment = MagicMock()
    comment.body = "Please set a resolution.\n\n<!-- AUTO_GENERATED_MISSING_RESOLUTION -->"

    mock_jira_client.search_issues.return_value = [issue1]
    mock_jira_client.get_comments.return_value = [comment]

    res = await jira_closed_missing_resolution_task()

    assert res == "Jira closed missing resolution reminder task completed."
    mock_llm.ainvoke.assert_not_called()
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_no_openai_key(mocker):
    mock = MagicMock()
    mock.get.return_value = ""
    mocker.patch("app.tasks.settings", mock)

    res = await jira_closed_missing_resolution_task()
    assert "skipped" in res
