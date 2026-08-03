import pytest
from app.tasks import jira_weekly_sprint_summary_task

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.MagicMock()
    mock.get.side_effect = lambda k, default="": (
        "fake_openai_key" if k == "OPENAI_API_KEY" else
        "TEST_SPACE" if k == "CONFLUENCE_TRACKED_SPACES" else
        "PROJ" if k == "JIRA_TRACKED_PROJECTS" else
        default
    )
    mocker.patch('app.tasks.settings', mock)
    return mock

@pytest.mark.asyncio
async def test_jira_weekly_sprint_summary_task_success(mocker, mock_settings):
    # Mock LLM
    mock_llm_instance = mocker.MagicMock()
    mock_llm_response = mocker.MagicMock()
    mock_llm_response.content = "<div>Test Summary</div>"
    mock_llm_instance.invoke.return_value = mock_llm_response
    mocker.patch('app.tasks.ChatOpenAI', return_value=mock_llm_instance)

    # Mock JiraClient
    mock_jira_client_cls = mocker.patch('app.tasks.JiraClient')
    mock_jira_client = mock_jira_client_cls.return_value

    # Create mock issues
    mock_issue_done = mocker.MagicMock()
    mock_issue_done.key = "PROJ-1"
    mock_issue_done.fields.summary = "Done Task"
    mock_issue_done.fields.status.name = "Done"
    mock_issue_done.fields.status.statusCategory.name = "Done"

    mock_issue_pending = mocker.MagicMock()
    mock_issue_pending.key = "PROJ-2"
    mock_issue_pending.fields.summary = "Pending Task"
    mock_issue_pending.fields.status.name = "In Progress"
    mock_issue_pending.fields.status.statusCategory.name = "In Progress"

    mock_jira_client.search_issues.return_value = [mock_issue_done, mock_issue_pending]

    # Mock ConfluenceClient
    mock_confluence_client_cls = mocker.patch('app.tasks.ConfluenceClient')
    mock_confluence_client = mock_confluence_client_cls.return_value

    result = await jira_weekly_sprint_summary_task()

    assert result == "Jira weekly sprint summary task completed"
    mock_jira_client.search_issues.assert_called_once_with('project = "PROJ" AND sprint in openSprints()')
    mock_llm_instance.invoke.assert_called_once()

    # Check that prompt contains pending and completed tasks properly mapped
    prompt_sent = mock_llm_instance.invoke.call_args[0][0][0].content
    assert "[PROJ-1] Done Task (Статус: Done)" in prompt_sent
    assert "[PROJ-2] Pending Task (Статус: In Progress)" in prompt_sent

    mock_confluence_client.client.create_page.assert_called_once_with(
        space="TEST_SPACE",
        title="Еженедельный отчет по спринту: PROJ",
        body="<div>Test Summary</div>",
        parent_id=None
    )


@pytest.mark.asyncio
async def test_jira_weekly_sprint_summary_task_no_openai_key(mocker):
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default="": "" if k == "OPENAI_API_KEY" else default
    mocker.patch('app.tasks.settings', mock_settings)

    result = await jira_weekly_sprint_summary_task()
    assert result == "Jira weekly sprint summary task skipped (no OpenAI API key)"


@pytest.mark.asyncio
async def test_jira_weekly_sprint_summary_task_no_confluence_space(mocker):
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default="": (
        "fake_key" if k == "OPENAI_API_KEY" else
        "" if k == "CONFLUENCE_TRACKED_SPACES" else
        default
    )
    mocker.patch('app.tasks.settings', mock_settings)

    result = await jira_weekly_sprint_summary_task()
    assert result == "Jira weekly sprint summary task skipped (no spaces)"


@pytest.mark.asyncio
async def test_jira_weekly_sprint_summary_task_no_issues(mocker, mock_settings):
    # Mock JiraClient to return empty list
    mock_jira_client_cls = mocker.patch('app.tasks.JiraClient')
    mock_jira_client = mock_jira_client_cls.return_value
    mock_jira_client.search_issues.return_value = []

    mock_confluence_client_cls = mocker.patch('app.tasks.ConfluenceClient')
    mock_confluence_client = mock_confluence_client_cls.return_value

    mock_llm_instance = mocker.MagicMock()
    mocker.patch('app.tasks.ChatOpenAI', return_value=mock_llm_instance)

    result = await jira_weekly_sprint_summary_task()

    assert result == "Jira weekly sprint summary task completed"
    mock_llm_instance.invoke.assert_not_called()
    mock_confluence_client.client.create_page.assert_not_called()

@pytest.mark.asyncio
async def test_jira_weekly_sprint_summary_task_html_cleanup(mocker, mock_settings):
    # Mock LLM to return wrapped HTML
    mock_llm_instance = mocker.MagicMock()
    mock_llm_response = mocker.MagicMock()
    mock_llm_response.content = "```html\n<div>Test Summary</div>\n```"
    mock_llm_instance.invoke.return_value = mock_llm_response
    mocker.patch('app.tasks.ChatOpenAI', return_value=mock_llm_instance)

    # Mock JiraClient
    mock_jira_client_cls = mocker.patch('app.tasks.JiraClient')
    mock_jira_client = mock_jira_client_cls.return_value
    mock_issue_done = mocker.MagicMock()
    mock_issue_done.key = "PROJ-1"
    mock_issue_done.fields.summary = "Done Task"
    mock_issue_done.fields.status.name = "Done"
    mock_issue_done.fields.status.statusCategory.name = "Done"
    mock_jira_client.search_issues.return_value = [mock_issue_done]

    # Mock ConfluenceClient
    mock_confluence_client_cls = mocker.patch('app.tasks.ConfluenceClient')
    mock_confluence_client = mock_confluence_client_cls.return_value

    await jira_weekly_sprint_summary_task()

    mock_confluence_client.client.create_page.assert_called_once_with(
        space="TEST_SPACE",
        title="Еженедельный отчет по спринту: PROJ",
        body="<div>Test Summary</div>",
        parent_id=None
    )
