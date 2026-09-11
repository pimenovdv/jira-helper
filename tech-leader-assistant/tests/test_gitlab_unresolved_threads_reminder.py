import pytest
from unittest.mock import MagicMock
import app.tasks as tasks
from app.tasks import gitlab_unresolved_threads_reminder_task
import datetime

@pytest.fixture
def mock_settings(mocker):
    mock = MagicMock()
    mock.get.side_effect = lambda k, default="": "fake_key" if k == "OPENAI_API_KEY" else "1" if k == "GITLAB_TRACKED_PROJECTS" else default
    mocker.patch('app.tasks.settings', mock)
    return mock

@pytest.fixture(autouse=True)
def mock_astext(monkeypatch):
    from sqlalchemy.sql.elements import BinaryExpression
    monkeypatch.setattr(BinaryExpression, "astext", property(lambda self: self), raising=False)

@pytest.mark.asyncio
async def test_gitlab_unresolved_threads_reminder_task(mocker, mock_settings):
    # Mock LLM
    mock_llm_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Reminder comment"
    mock_llm_instance.ainvoke = mocker.AsyncMock(return_value=mock_response)
    mocker.patch('app.tasks.ChatOpenAI', return_value=mock_llm_instance)

    # Mock GitLab Client
    mock_gitlab_client_class = mocker.patch('app.tasks.GitLabClient', autospec=True)
    mock_client_instance = mock_gitlab_client_class.return_value
    mock_client_instance.client = MagicMock()

    mock_project = MagicMock()
    mock_client_instance.client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.title = "Test MR"
    mock_mr.iid = 1
    mock_project.mergerequests.list.return_value = [mock_mr]

    # Mock discussions
    mock_discussion = MagicMock()
    now = datetime.datetime.now(datetime.timezone.utc)
    old_date = (now - datetime.timedelta(days=4)).isoformat()

    mock_note = {
        'resolvable': True,
        'resolved': False,
        'updated_at': old_date,
        'body': 'Initial comment'
    }

    mock_discussion.attributes = {'notes': [mock_note]}
    mock_discussion.notes = MagicMock()

    mock_mr.discussions.list.return_value = [mock_discussion]

    result = await gitlab_unresolved_threads_reminder_task()

    assert result == "GitLab unresolved threads reminder task completed"
    mock_discussion.notes.create.assert_called_once_with({'body': 'Reminder comment'})
    mock_llm_instance.ainvoke.assert_called_once()

    # Test skipped path (already reminded)
    mock_discussion.notes.create.reset_mock()
    mock_llm_instance.ainvoke.reset_mock()

    mock_note_already_reminded = {
        'resolvable': False,
        'resolved': False,
        'updated_at': old_date,
        'body': '<!-- AUTO_GENERATED_UNRESOLVED_THREAD_REMINDER -->'
    }
    mock_discussion.attributes['notes'].append(mock_note_already_reminded)

    await gitlab_unresolved_threads_reminder_task()

    mock_discussion.notes.create.assert_not_called()
    mock_llm_instance.ainvoke.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_unresolved_threads_reminder_task_no_api_key(mocker):
    mock = MagicMock()
    mock.get.side_effect = lambda k, default="": "" if k == "OPENAI_API_KEY" else "1" if k == "GITLAB_TRACKED_PROJECTS" else default
    mocker.patch('app.tasks.settings', mock)

    result = await gitlab_unresolved_threads_reminder_task()
    assert result == "GitLab unresolved threads reminder task skipped (no OpenAI API key)"
