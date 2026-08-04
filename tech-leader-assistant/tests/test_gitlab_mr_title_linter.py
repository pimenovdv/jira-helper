import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_title_linter_task
import app.tasks

@pytest.fixture
def mock_dependencies(mocker):
    # Mock settings
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda k, d="": {
        "OPENAI_API_KEY": "test-key",
        "GITLAB_TRACKED_PROJECTS": "123, 456"
    }.get(k, d)
    mocker.patch("app.tasks.settings", mock_settings)

    # Mock GitLabClient
    mock_gitlab = MagicMock()
    mocker.patch("app.tasks.GitLabClient", return_value=mock_gitlab)

    # Mock ChatOpenAI
    mock_llm_instance = MagicMock()
    mock_llm_instance.invoke.return_value = MagicMock(content="Пожалуйста, исправьте название.")
    mocker.patch("app.tasks.ChatOpenAI", return_value=mock_llm_instance)

    return mock_gitlab, mock_llm_instance

@pytest.mark.asyncio
async def test_gitlab_mr_title_linter_no_api_key(mocker):
    mock_settings = MagicMock()
    mock_settings.get.return_value = ""
    mocker.patch("app.tasks.settings", mock_settings)

    result = await gitlab_mr_title_linter_task()
    assert result == "MR title linter task skipped (no OpenAI API key)"

@pytest.mark.asyncio
async def test_gitlab_mr_title_linter_success(mock_dependencies):
    mock_gitlab, mock_llm = mock_dependencies

    # Setup mock MRs
    mr1 = MagicMock()
    mr1.iid = 1
    mr1.title = "bad title"
    mr1.draft = False

    mr2 = MagicMock()
    mr2.iid = 2
    mr2.title = "feat(ui): good title"
    mr2.draft = False

    mr3 = MagicMock()
    mr3.iid = 3
    mr3.title = "Draft: still bad title but draft"
    mr3.draft = False

    mr4 = MagicMock()
    mr4.iid = 4
    mr4.title = "TLA-123 Good Jira Title"
    mr4.draft = False

    mock_gitlab.get_open_merge_requests.side_effect = lambda pid: [mr1, mr2, mr3, mr4] if pid == "123" else []

    # Mock notes
    mock_note = MagicMock()
    mock_note.body = "Some comment"
    mock_gitlab.get_mr_notes.return_value = [mock_note]

    result = await gitlab_mr_title_linter_task()

    assert result == "GitLab MR title linter task completed"

    # It should have checked 2 projects
    assert mock_gitlab.get_open_merge_requests.call_count == 2

    # It should only complain about mr1
    mock_gitlab.create_mr_note.assert_called_once()
    args, kwargs = mock_gitlab.create_mr_note.call_args
    assert args[0] == "123"
    assert args[1] == 1
    assert "Пожалуйста, исправьте название." in args[2]
    assert "<!-- AUTO_GENERATED_MR_TITLE_LINTER_REMINDER -->" in args[2]

@pytest.mark.asyncio
async def test_gitlab_mr_title_linter_already_reminded(mock_dependencies):
    mock_gitlab, mock_llm = mock_dependencies

    mr1 = MagicMock()
    mr1.iid = 1
    mr1.title = "bad title"
    mr1.draft = False

    mock_gitlab.get_open_merge_requests.return_value = [mr1]

    # Mock notes with the marker
    mock_note = MagicMock()
    mock_note.body = "Пожалуйста, исправьте название.\n\n<!-- AUTO_GENERATED_MR_TITLE_LINTER_REMINDER -->"
    mock_gitlab.get_mr_notes.return_value = [mock_note]

    await gitlab_mr_title_linter_task()

    # Should not post again
    mock_gitlab.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_title_linter_exceptions(mock_dependencies):
    mock_gitlab, mock_llm = mock_dependencies

    # Setup exception on get_open_merge_requests
    mock_gitlab.get_open_merge_requests.side_effect = Exception("API error")

    result = await gitlab_mr_title_linter_task()
    assert result == "GitLab MR title linter task completed"

    # Setup exception on get_mr_notes
    mr1 = MagicMock()
    mr1.iid = 1
    mr1.title = "bad title"
    mr1.draft = False
    mock_gitlab.get_open_merge_requests.side_effect = lambda pid: [mr1]
    mock_gitlab.get_mr_notes.side_effect = Exception("Notes API error")

    result = await gitlab_mr_title_linter_task()
    assert result == "GitLab MR title linter task completed"
    mock_gitlab.create_mr_note.assert_not_called()
