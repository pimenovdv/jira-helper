import pytest
from unittest.mock import patch, MagicMock
from app.tasks import automated_code_review_task
from langchain_core.messages import AIMessage

@pytest.mark.asyncio
async def test_automated_code_review_task(mocker):
    # Mock settings to return a tracked project string
    from app.clients import settings
    original_projects = settings.get('GITLAB_TRACKED_PROJECTS')
    settings.set('GITLAB_TRACKED_PROJECTS', 'proj1')

    # Mock GitLabClient
    mock_gl_instance = MagicMock()
    mock_gl_class = mocker.patch('app.tasks.GitLabClient', return_value=mock_gl_instance)

    mock_mr = MagicMock()
    mock_mr.iid = 1
    mock_mr.title = "TASK-1: Implementation"
    mock_mr.author = {"username": "dev1"}

    mock_gl_instance.get_project_merge_requests.return_value = [mock_mr]

    # Mock MR changes
    mock_gl_instance.get_merge_request_changes.return_value = {
        "changes": [
            {
                "new_path": "main.py",
                "diff": "+ print('hello')\n- print('world')"
            }
        ]
    }

    # Mock OpenSearchClient
    mock_os_instance = MagicMock()
    mock_os_class = mocker.patch('app.clients.opensearch_client.OpenSearchClient', return_value=mock_os_instance)

    mock_os_instance.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "content": "All code must be documented in Russian.",
                        "url": "http://confluence/guidelines"
                    }
                }
            ]
        }
    }

    # Mock LangChain LLM
    mock_llm_instance = MagicMock()
    mock_llm_class = mocker.patch('app.tasks.ChatOpenAI', return_value=mock_llm_instance)

    mock_llm_instance.invoke.return_value = AIMessage(content="Код выглядит хорошо, но нужно добавить документацию.")

    # Call the task
    await automated_code_review_task()
    settings.set('GITLAB_TRACKED_PROJECTS', original_projects)

    # Assertions
    mock_gl_instance.get_project_merge_requests.assert_any_call("proj1", state="opened")
    mock_gl_instance.get_merge_request_changes.assert_any_call("proj1", 1)

    # Check if create_mr_note was called
    assert mock_gl_instance.create_mr_note.call_count == 1

    # Verify the note content includes the LLM response
    call_args = mock_gl_instance.create_mr_note.call_args[0]
    assert call_args[0] == "proj1"
    assert call_args[1] == 1
    assert "Код выглядит хорошо" in call_args[2]
