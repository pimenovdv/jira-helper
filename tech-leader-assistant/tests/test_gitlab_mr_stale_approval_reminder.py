import pytest
from unittest.mock import MagicMock, call
from datetime import datetime, timezone, timedelta
from app.tasks import gitlab_mr_stale_approval_reminder_task

@pytest.fixture
def mock_settings(mocker):
    settings_mock = mocker.patch("app.tasks.settings")
    settings_mock.get.side_effect = lambda k, default=None: "project1" if k == "GITLAB_TRACKED_PROJECTS" else "fake_key" if k == "OPENAI_API_KEY" else default
    return settings_mock

@pytest.fixture
def mock_gitlab_client(mocker):
    client_mock = mocker.patch("app.tasks.GitLabClient").return_value
    return client_mock

@pytest.fixture
def mock_chat_openai(mocker):
    llm_mock = mocker.patch("app.tasks.ChatOpenAI").return_value
    llm_mock.ainvoke = mocker.AsyncMock()
    llm_mock.ainvoke.return_value.content = "Test reminder comment."
    return llm_mock

@pytest.mark.asyncio
async def test_gitlab_mr_stale_approval_reminder_no_api_key(mocker):
    settings_mock = mocker.patch("app.tasks.settings")
    settings_mock.get.side_effect = lambda k, default=None: "" if k == "OPENAI_API_KEY" else default

    result = await gitlab_mr_stale_approval_reminder_task()
    assert result == "GitLab MR stale approval reminder task skipped (no OpenAI API key)"

@pytest.mark.asyncio
async def test_gitlab_mr_stale_approval_reminder_recently_updated(mock_settings, mock_gitlab_client, mock_chat_openai):
    mr_mock = MagicMock()
    mr_mock.draft = False
    mr_mock.title = "Feature"
    mr_mock.iid = 1
    # Updated 1 day ago
    mr_mock.updated_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    mock_gitlab_client.get_merge_requests.return_value = [mr_mock]

    result = await gitlab_mr_stale_approval_reminder_task()

    assert result == "GitLab MR stale approval reminder task completed."
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_stale_approval_reminder_no_approvals(mock_settings, mock_gitlab_client, mock_chat_openai):
    mr_mock = MagicMock()
    mr_mock.draft = False
    mr_mock.title = "Feature"
    mr_mock.iid = 1
    # Updated 5 days ago
    mr_mock.updated_at = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

    approvals_mock = MagicMock()
    approvals_mock.approved_by = [] # No approvals
    mr_mock.approvals.get.return_value = approvals_mock

    mock_gitlab_client.get_merge_requests.return_value = [mr_mock]

    result = await gitlab_mr_stale_approval_reminder_task()

    assert result == "GitLab MR stale approval reminder task completed."
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_stale_approval_reminder_already_reminded(mock_settings, mock_gitlab_client, mock_chat_openai):
    mr_mock = MagicMock()
    mr_mock.draft = False
    mr_mock.title = "Feature"
    mr_mock.iid = 1
    mr_mock.updated_at = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

    approvals_mock = MagicMock()
    approvals_mock.approved_by = [{"user": {"username": "reviewer"}}]
    mr_mock.approvals.get.return_value = approvals_mock

    note_mock = MagicMock()
    note_mock.body = "Some text <!-- AUTO_GENERATED_STALE_APPROVAL_REMINDER -->"
    mr_mock.notes.list.return_value = [note_mock]

    mock_gitlab_client.get_merge_requests.return_value = [mr_mock]

    result = await gitlab_mr_stale_approval_reminder_task()

    assert result == "GitLab MR stale approval reminder task completed."
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_stale_approval_reminder_sends_reminder(mock_settings, mock_gitlab_client, mock_chat_openai):
    mr_mock = MagicMock()
    mr_mock.draft = False
    mr_mock.title = "Feature"
    mr_mock.iid = 1
    mr_mock.updated_at = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    mr_mock.author = {"username": "test_author"}

    approvals_mock = MagicMock()
    approvals_mock.approved_by = [{"user": {"username": "reviewer"}}]
    mr_mock.approvals.get.return_value = approvals_mock

    note_mock = MagicMock()
    note_mock.body = "Just a normal comment"
    mr_mock.notes.list.return_value = [note_mock]

    mock_gitlab_client.get_merge_requests.return_value = [mr_mock]

    result = await gitlab_mr_stale_approval_reminder_task()

    assert result == "GitLab MR stale approval reminder task completed."
    mock_chat_openai.ainvoke.assert_called_once()
    mock_gitlab_client.create_mr_note.assert_called_once_with(
        "project1",
        1,
        "Test reminder comment.\n\n<!-- AUTO_GENERATED_STALE_APPROVAL_REMINDER -->"
    )
