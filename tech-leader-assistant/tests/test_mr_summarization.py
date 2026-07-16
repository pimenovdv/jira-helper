import pytest
import os
from unittest.mock import MagicMock

# Set env before importing
os.environ['OPENAI_API_KEY'] = 'test-api-key'

from app.tasks import mr_summarization_task

@pytest.mark.asyncio
async def test_mr_summarization_task(mocker):
    def mock_settings_get(key, default=''):
        if key == 'GITLAB_TRACKED_PROJECTS': return 'proj1'
        if key == 'OPENAI_API_KEY': return 'test-key'
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)

    # Mock GitLabClient
    mock_gl_instance = MagicMock()

    mock_mr1 = MagicMock()
    mock_mr1.iid = 1
    mock_note_already_summarized = MagicMock()
    mock_note_already_summarized.body = "<!-- AUTO_GENERATED_MR_SUMMARY -->\n\nsummary"
    mock_mr1.notes.list.return_value = [mock_note_already_summarized]

    mock_mr2 = MagicMock()
    mock_mr2.iid = 2
    mock_note_not_summarized = MagicMock()
    mock_note_not_summarized.body = "Just a regular comment"
    mock_mr2.notes.list.return_value = [mock_note_not_summarized]

    mock_mr3 = MagicMock()
    mock_mr3.iid = 3
    mock_mr3.notes.list.return_value = []

    mock_mr4 = MagicMock()
    mock_mr4.iid = 4
    mock_mr4.notes.list.side_effect = Exception("Note fetch failed")

    # ensure it returns exactly these 4 mock MRs
    mock_gl_instance.get_project_merge_requests.return_value = [mock_mr1, mock_mr2, mock_mr3, mock_mr4]

    def get_changes_mock(project_id, iid):
        if iid == 2:
            return {'changes': [{'diff': '+ new line'}]}
        elif iid == 3:
            return {'changes': [{'diff': ''}]}
        return {}

    mock_gl_instance.get_merge_request_changes.side_effect = get_changes_mock

    mocker.patch('app.tasks.GitLabClient', return_value=mock_gl_instance)

    # Mock LLM
    mock_llm_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Summary of changes"
    mock_llm_instance.invoke.return_value = mock_response
    mocker.patch('app.tasks.ChatOpenAI', return_value=mock_llm_instance)

    await mr_summarization_task()

    # Verification
    # Only MR 2 should trigger a create_mr_note call
    mock_gl_instance.create_mr_note.assert_called_once_with('proj1', 2, "<!-- AUTO_GENERATED_MR_SUMMARY -->\n\nSummary of changes")

@pytest.mark.asyncio
async def test_mr_summarization_task_large_diff(mocker):
    def mock_settings_get(key, default=''):
        if key == 'GITLAB_TRACKED_PROJECTS': return 'proj1'
        if key == 'OPENAI_API_KEY': return 'test-key'
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)

    mock_gl_instance = MagicMock()
    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.notes.list.return_value = []
    mock_gl_instance.get_project_merge_requests.return_value = [mock_mr]

    large_diff = "A" * 10005
    mock_gl_instance.get_merge_request_changes.return_value = {'changes': [{'diff': large_diff}]}

    mocker.patch('app.tasks.GitLabClient', return_value=mock_gl_instance)

    mock_llm_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Summary of changes"
    mock_llm_instance.invoke.return_value = mock_response
    mocker.patch('app.tasks.ChatOpenAI', return_value=mock_llm_instance)

    await mr_summarization_task()

    mock_gl_instance.create_mr_note.assert_called_once()

    args, _ = mock_llm_instance.invoke.call_args
    prompt_content = args[0][0].content
    assert "...[diff truncated]" in prompt_content
    assert len(prompt_content) < 11000

@pytest.mark.asyncio
async def test_mr_summarization_task_project_exception(mocker):
    def mock_settings_get(key, default=''):
        if key == 'GITLAB_TRACKED_PROJECTS': return 'proj1'
        if key == 'OPENAI_API_KEY': return 'test-key'
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)

    mock_gl_instance = MagicMock()
    mock_gl_instance.get_project_merge_requests.side_effect = Exception("Project fetch failed")
    mocker.patch('app.tasks.GitLabClient', return_value=mock_gl_instance)

    mocker.patch('app.tasks.ChatOpenAI')

    await mr_summarization_task()

    mock_gl_instance.create_mr_note.assert_not_called()
