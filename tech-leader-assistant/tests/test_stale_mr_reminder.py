import pytest
from app.tasks import stale_mr_reminder_task
from datetime import datetime, timezone, timedelta

@pytest.fixture
def override_settings():
    original_api = settings.get("OPENAI_API_KEY")
    original_projects = settings.get("GITLAB_TRACKED_PROJECTS")
    settings.set("OPENAI_API_KEY", "test-key")
    settings.set("GITLAB_TRACKED_PROJECTS", "123, 456")
    yield
    settings.set("OPENAI_API_KEY", original_api)
    settings.set("GITLAB_TRACKED_PROJECTS", original_projects)

@pytest.fixture
def mock_gitlab_client(mocker):
    return mocker.patch('app.tasks.GitLabClient')

@pytest.fixture
def mock_chat_openai(mocker):
    return mocker.patch('app.tasks.ChatOpenAI')

from app.clients import settings
@pytest.mark.asyncio
async def test_stale_mr_reminder_no_api_key():
    original = settings.get("OPENAI_API_KEY")
    settings.set("OPENAI_API_KEY", "")
    result = await stale_mr_reminder_task()
    assert result == "Stale MR reminder task skipped (no OpenAI API key)"
    settings.set("OPENAI_API_KEY", original)

@pytest.mark.asyncio
async def test_stale_mr_reminder_task(override_settings, mock_gitlab_client, mock_chat_openai, mocker):
    now = datetime.now(timezone.utc)

    # Setup mocked GitLabClient instance
    mock_gl_instance = mock_gitlab_client.return_value

    class MockNote:
        def __init__(self, body):
            self.body = body

    class MockNotesManager:
        def __init__(self, notes):
            self.notes = notes
        def list(self, all=True):
            return self.notes

    class MockMR:
        def __init__(self, iid, title, updated_at, notes):
            self.iid = iid
            self.title = title
            self.updated_at = updated_at
            self.notes = MockNotesManager(notes)

    # MR 1: updated 10 days ago, no reminder
    updated_at_stale = (now - timedelta(days=10)).isoformat().replace("+00:00", "Z")
    mr_stale_no_reminder = MockMR(1, "Stale MR 1", updated_at_stale, [])

    # MR 2: updated 2 days ago, no reminder
    updated_at_fresh = (now - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    mr_fresh = MockMR(2, "Fresh MR", updated_at_fresh, [])

    # MR 3: updated 10 days ago, already reminded
    mr_stale_reminded = MockMR(3, "Stale MR 2", updated_at_stale, [MockNote("Some note"), MockNote("<!-- AUTO_GENERATED_STALE_MR_REMINDER -->\nReminder!")])

    # Assign MRs to projects
    def mock_get_mrs(project_id, state):
        if project_id == "123":
            return [mr_stale_no_reminder, mr_fresh]
        elif project_id == "456":
            return [mr_stale_reminded]
        return []

    mock_gl_instance.get_project_merge_requests.side_effect = mock_get_mrs

    # Setup mocked ChatOpenAI instance
    mock_llm_instance = mock_chat_openai.return_value
    mock_response = mocker.Mock()
    mock_response.content = "Please review this stale MR."
    mock_llm_instance.invoke.return_value = mock_response

    await stale_mr_reminder_task()

    # Verify LLM was called exactly once (for mr_stale_no_reminder)
    assert mock_llm_instance.invoke.call_count == 1

    # Verify a note was created on project 123, mr iid 1
    mock_gl_instance.create_mr_note.assert_called_once_with("123", 1, "<!-- AUTO_GENERATED_STALE_MR_REMINDER -->\n\nPlease review this stale MR.")
