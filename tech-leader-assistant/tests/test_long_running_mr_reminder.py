import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_long_running_mr_reminder_task
from datetime import datetime, timezone, timedelta

@pytest.fixture(autouse=True)
def mock_astext(monkeypatch):
    from sqlalchemy.sql.elements import BinaryExpression
    monkeypatch.setattr(BinaryExpression, "astext", property(lambda self: self), raising=False)

@pytest.mark.asyncio
async def test_gitlab_long_running_mr_reminder_task_posts_message(mocker):
    # Mock settings
    def mock_settings_get(key, default=""):
        if key == "GITLAB_TRACKED_PROJECTS":
            return "1"
        if key == "OPENAI_API_KEY":
            return "test_key"
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)

    # Mock ChatOpenAI
    mock_llm_cls = mocker.patch('app.tasks.ChatOpenAI')
    mock_llm = mock_llm_cls.return_value
    mock_llm_response = MagicMock()
    mock_llm_response.content = "Тестовое сообщение"
    mock_llm.invoke.return_value = mock_llm_response

    # Mock GitLabClient
    mock_gitlab_client_cls = mocker.patch('app.tasks.GitLabClient')
    mock_gitlab_client = mock_gitlab_client_cls.return_value

    mock_mr = MagicMock()
    mock_mr.iid = 123
    mock_mr.title = "Test MR"
    # Set created_at to 15 days ago
    old_date = datetime.now(timezone.utc) - timedelta(days=15)
    mock_mr.created_at = old_date.isoformat().replace('+00:00', 'Z')

    # Mock notes
    mock_note = MagicMock()
    mock_note.body = "Some regular comment"
    mock_mr.notes.list.return_value = [mock_note]

    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr]

    # Run the task
    result = await gitlab_long_running_mr_reminder_task()

    assert result == "GitLab long-running MR reminder task completed"
    mock_gitlab_client.get_project_merge_requests.assert_called_once_with("1", state="opened")
    mock_mr.notes.list.assert_called_once_with(all=True)
    mock_llm.invoke.assert_called_once()
    mock_gitlab_client.create_mr_note.assert_called_once_with("1", 123, "Тестовое сообщение\n\n<!-- AUTO_GENERATED_LONG_RUNNING_MR_REMINDER -->")

@pytest.mark.asyncio
async def test_gitlab_long_running_mr_reminder_task_already_reminded(mocker):
    # Mock settings
    def mock_settings_get(key, default=""):
        if key == "GITLAB_TRACKED_PROJECTS":
            return "1"
        if key == "OPENAI_API_KEY":
            return "test_key"
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)

    mock_llm_cls = mocker.patch('app.tasks.ChatOpenAI')
    mock_llm = mock_llm_cls.return_value

    # Mock GitLabClient
    mock_gitlab_client_cls = mocker.patch('app.tasks.GitLabClient')
    mock_gitlab_client = mock_gitlab_client_cls.return_value

    mock_mr = MagicMock()
    mock_mr.iid = 123
    old_date = datetime.now(timezone.utc) - timedelta(days=15)
    mock_mr.created_at = old_date.isoformat().replace('+00:00', 'Z')

    # Mock notes with marker
    mock_note = MagicMock()
    mock_note.body = "Some comment\n\n<!-- AUTO_GENERATED_LONG_RUNNING_MR_REMINDER -->"
    mock_mr.notes.list.return_value = [mock_note]

    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr]

    # Run the task
    result = await gitlab_long_running_mr_reminder_task()

    assert result == "GitLab long-running MR reminder task completed"
    mock_gitlab_client.get_project_merge_requests.assert_called_once_with("1", state="opened")
    mock_mr.notes.list.assert_called_once_with(all=True)
    mock_llm.invoke.assert_not_called()
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_long_running_mr_reminder_task_recent_mr(mocker):
    # Mock settings
    def mock_settings_get(key, default=""):
        if key == "GITLAB_TRACKED_PROJECTS":
            return "1"
        if key == "OPENAI_API_KEY":
            return "test_key"
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)

    mock_llm_cls = mocker.patch('app.tasks.ChatOpenAI')
    mock_llm = mock_llm_cls.return_value

    # Mock GitLabClient
    mock_gitlab_client_cls = mocker.patch('app.tasks.GitLabClient')
    mock_gitlab_client = mock_gitlab_client_cls.return_value

    mock_mr = MagicMock()
    mock_mr.iid = 123
    # Set created_at to 5 days ago
    recent_date = datetime.now(timezone.utc) - timedelta(days=5)
    mock_mr.created_at = recent_date.isoformat().replace('+00:00', 'Z')

    mock_gitlab_client.get_project_merge_requests.return_value = [mock_mr]

    # Run the task
    result = await gitlab_long_running_mr_reminder_task()

    assert result == "GitLab long-running MR reminder task completed"
    mock_gitlab_client.get_project_merge_requests.assert_called_once_with("1", state="opened")
    mock_mr.notes.list.assert_not_called()
    mock_llm.invoke.assert_not_called()
    mock_gitlab_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_long_running_mr_reminder_task_no_api_key(mocker):
    def mock_settings_get(key, default=""):
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)

    result = await gitlab_long_running_mr_reminder_task()
    assert result == "GitLab long-running MR reminder task skipped (no OpenAI API key)"
