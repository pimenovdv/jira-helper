import pytest
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage
from app.tasks import gitlab_mr_missing_reviewer_notifier_task

@pytest.mark.asyncio
async def test_gitlab_mr_missing_reviewer_notifier_success(mocker):
    # Mock settings
    mock_settings = mocker.patch('app.tasks.settings')
    mock_settings.get.side_effect = lambda k, d="": {
        "OPENAI_API_KEY": "fake_key",
        "GITLAB_TRACKED_PROJECTS": "123"
    }.get(k, d)

    # Mock GitLab Client
    mock_gl_client_class = mocker.patch('app.tasks.GitLabClient')
    mock_gl_client_instance = mock_gl_client_class.return_value
    mock_project = MagicMock()
    mock_gl_client_instance.client.projects.get.return_value = mock_project

    # Mock MR
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.title = "Test MR"
    mock_mr.draft = False
    mock_mr.reviewers = []

    # Mock Notes (no previous reminder)
    mock_note = MagicMock()
    mock_note.body = "Some regular comment"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project.mergerequests.list.return_value = [mock_mr]

    # Mock LLM
    mock_llm_class = mocker.patch('app.tasks.ChatOpenAI')
    mock_llm_instance = mock_llm_class.return_value
    mock_response = MagicMock()
    mock_response.content = "Please assign a reviewer."
    mock_llm_instance.ainvoke = mocker.AsyncMock(return_value=mock_response)

    # Run the task
    result = await gitlab_mr_missing_reviewer_notifier_task()

    # Assertions
    mock_llm_instance.ainvoke.assert_called_once()
    mock_gl_client_instance.create_mr_note.assert_called_once_with(
        "123", 1, "Please assign a reviewer."
    )

@pytest.mark.asyncio
async def test_gitlab_mr_missing_reviewer_notifier_no_api_key(mocker):
    # Mock settings to return no API key
    mock_settings = mocker.patch('app.tasks.settings')
    mock_settings.get.side_effect = lambda k, d="": {
        "OPENAI_API_KEY": "",
        "GITLAB_TRACKED_PROJECTS": "123"
    }.get(k, d)

    result = await gitlab_mr_missing_reviewer_notifier_task()

    assert result == "GitLab MR missing reviewer notifier task skipped (no OpenAI API key)"

@pytest.mark.asyncio
async def test_gitlab_mr_missing_reviewer_notifier_skip_draft(mocker):
    mock_settings = mocker.patch('app.tasks.settings')
    mock_settings.get.side_effect = lambda k, d="": {
        "OPENAI_API_KEY": "fake_key",
        "GITLAB_TRACKED_PROJECTS": "123"
    }.get(k, d)

    mock_gl_client_class = mocker.patch('app.tasks.GitLabClient')
    mock_gl_client_instance = mock_gl_client_class.return_value
    mock_project = MagicMock()
    mock_gl_client_instance.client.projects.get.return_value = mock_project

    # Mock Draft MR
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.draft = True
    mock_mr.reviewers = []

    mock_project.mergerequests.list.return_value = [mock_mr]

    mock_llm_class = mocker.patch('app.tasks.ChatOpenAI')

    await gitlab_mr_missing_reviewer_notifier_task()

    mock_llm_class.return_value.ainvoke.assert_not_called()
    mock_gl_client_instance.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_reviewer_notifier_skip_has_reviewers(mocker):
    mock_settings = mocker.patch('app.tasks.settings')
    mock_settings.get.side_effect = lambda k, d="": {
        "OPENAI_API_KEY": "fake_key",
        "GITLAB_TRACKED_PROJECTS": "123"
    }.get(k, d)

    mock_gl_client_class = mocker.patch('app.tasks.GitLabClient')
    mock_gl_client_instance = mock_gl_client_class.return_value
    mock_project = MagicMock()
    mock_gl_client_instance.client.projects.get.return_value = mock_project

    # Mock MR with reviewers
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.draft = False
    mock_mr.reviewers = [{"username": "reviewer1"}]

    mock_project.mergerequests.list.return_value = [mock_mr]

    mock_llm_class = mocker.patch('app.tasks.ChatOpenAI')

    await gitlab_mr_missing_reviewer_notifier_task()

    mock_llm_class.return_value.ainvoke.assert_not_called()
    mock_gl_client_instance.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_reviewer_notifier_already_notified(mocker):
    mock_settings = mocker.patch('app.tasks.settings')
    mock_settings.get.side_effect = lambda k, d="": {
        "OPENAI_API_KEY": "fake_key",
        "GITLAB_TRACKED_PROJECTS": "123"
    }.get(k, d)

    mock_gl_client_class = mocker.patch('app.tasks.GitLabClient')
    mock_gl_client_instance = mock_gl_client_class.return_value
    mock_project = MagicMock()
    mock_gl_client_instance.client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.draft = False
    mock_mr.reviewers = []

    # Mock Notes (has previous reminder)
    mock_note = MagicMock()
    mock_note.body = "<!-- AUTO_GENERATED_MR_MISSING_REVIEWER_NOTIFIER -->"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project.mergerequests.list.return_value = [mock_mr]

    mock_llm_class = mocker.patch('app.tasks.ChatOpenAI')

    await gitlab_mr_missing_reviewer_notifier_task()

    mock_llm_class.return_value.ainvoke.assert_not_called()
    mock_gl_client_instance.create_mr_note.assert_not_called()
