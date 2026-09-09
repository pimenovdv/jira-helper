import pytest
from unittest.mock import MagicMock

from app.tasks import jira_subtask_without_parent_warning_task

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch('app.tasks.settings')
    mock.get.side_effect = lambda key, default="": "test_key" if key == "OPENAI_API_KEY" else "PROJ1"

    # We also need to patch settings where JiraClient is imported/used, but if we mock JiraClient completely, it might be ok.
    # Wait, local import from app.clients import settings inside tasks.py.
    mock_clients_settings = mocker.patch('app.clients.settings')
    mock_clients_settings.get.side_effect = lambda key, default="": "test_key" if key == "OPENAI_API_KEY" else "PROJ1"
    return mock

@pytest.fixture
def mock_jira_client(mocker):
    mock_client = mocker.patch('app.tasks.JiraClient', autospec=True) # in case it uses global
    # Since it does local import inside the function: `from app.clients.jira_client import JiraClient`
    # We should patch `app.clients.jira_client.JiraClient`
    mock_real_client = mocker.patch('app.clients.jira_client.JiraClient', autospec=True)
    client_instance = mock_real_client.return_value
    client_instance.search_issues.return_value = []
    client_instance.get_comments.return_value = []
    return client_instance

@pytest.fixture
def mock_chat_openai(mocker):
    # ChatOpenAI is imported locally as well: `from langchain_openai import ChatOpenAI`
    mock_llm = mocker.patch('app.tasks.ChatOpenAI', autospec=True)
    # Also patch the global one if it exists or just patch langchain_openai.ChatOpenAI
    mock_real_llm = mocker.patch('langchain_openai.ChatOpenAI', autospec=True)

    llm_instance = mock_real_llm.return_value
    mock_response = MagicMock()
    mock_response.content = "Please link this subtask to a parent."
    llm_instance.invoke.return_value = mock_response

    llm_instance2 = mock_llm.return_value
    llm_instance2.invoke.return_value = mock_response
    return llm_instance

@pytest.mark.asyncio
async def test_jira_subtask_without_parent_warning_task_adds_comment(mock_settings, mock_jira_client, mock_chat_openai):
    # Mock a subtask without parent and another with a parent
    issue_no_parent = MagicMock()
    issue_no_parent.key = "PROJ1-123"
    issue_no_parent.fields = MagicMock()
    issue_no_parent.fields.parent = None

    issue_with_parent = MagicMock()
    issue_with_parent.key = "PROJ1-124"
    issue_with_parent.fields = MagicMock()
    issue_with_parent.fields.parent = MagicMock()

    mock_jira_client.search_issues.return_value = [issue_no_parent, issue_with_parent]

    # Run the task
    result = await jira_subtask_without_parent_warning_task()

    assert result == "Jira subtask without parent warning task completed"

    # Assert add_comment called only once for PROJ1-123
    mock_jira_client.add_comment.assert_called_once()
    args, kwargs = mock_jira_client.add_comment.call_args
    assert args[0] == "PROJ1-123"
    assert "Please link this subtask to a parent." in args[1]
    assert "<!-- AUTO_GENERATED_JIRA_SUBTASK_WITHOUT_PARENT -->" in args[1]


@pytest.mark.asyncio
async def test_jira_subtask_without_parent_warning_task_skips_if_already_commented(mock_settings, mock_jira_client, mock_chat_openai):
    issue_no_parent = MagicMock()
    issue_no_parent.key = "PROJ1-123"
    issue_no_parent.fields = MagicMock()
    issue_no_parent.fields.parent = None

    mock_jira_client.search_issues.return_value = [issue_no_parent]

    # Mock existing comment with the reminder marker
    mock_comment = MagicMock()
    mock_comment.body = "Existing comment <!-- AUTO_GENERATED_JIRA_SUBTASK_WITHOUT_PARENT -->"
    mock_jira_client.get_comments.return_value = [mock_comment]

    result = await jira_subtask_without_parent_warning_task()

    assert result == "Jira subtask without parent warning task completed"

    # Assert add_comment was not called since the comment already exists
    mock_jira_client.add_comment.assert_not_called()
