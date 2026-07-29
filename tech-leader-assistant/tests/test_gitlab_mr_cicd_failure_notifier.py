import pytest
from unittest.mock import MagicMock, AsyncMock

from app.tasks import gitlab_mr_cicd_failure_notifier_task

@pytest.mark.asyncio
async def test_gitlab_mr_cicd_failure_notifier_skip_no_api_key(mocker):
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda k, d="": "" if k == "OPENAI_API_KEY" else d
    mocker.patch("app.tasks.settings", mock_settings)

    result = await gitlab_mr_cicd_failure_notifier_task()
    assert "skipped (no OpenAI API key)" in result

@pytest.mark.asyncio
async def test_gitlab_mr_cicd_failure_notifier_task(mocker):
    mock_settings = MagicMock()
    def settings_get(key, default=""):
        if key == "OPENAI_API_KEY":
            return "fake-key"
        if key == "GITLAB_TRACKED_PROJECTS":
            return "proj1"
        return default
    mock_settings.get.side_effect = settings_get
    mocker.patch("app.tasks.settings", mock_settings)

    # Mock ChatOpenAI
    mock_llm_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Please fix your CI! <!-- AUTO_GENERATED_CI_FAILURE_NOTIFIER_999 -->"
    mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
    mocker.patch("app.tasks.ChatOpenAI", return_value=mock_llm_instance)

    # Mock GitLab Client and objects
    mock_gl_client_class = MagicMock()
    mock_gl_instance = MagicMock()
    mock_gl_client_class.return_value = mock_gl_instance
    mocker.patch("app.tasks.GitLabClient", mock_gl_client_class)

    mock_project = MagicMock()
    mock_gl_instance.client.projects.get.return_value = mock_project

    # MR1: CI failed, already notified
    mock_mr1 = MagicMock()
    mock_mr1.title = "MR 1"
    mock_mr1.iid = 1
    mock_pipeline1 = MagicMock()
    mock_pipeline1.status = 'failed'
    mock_pipeline1.id = 111
    mock_mr1.pipelines.list.return_value = [mock_pipeline1]

    mock_note1 = MagicMock()
    mock_note1.body = "<!-- AUTO_GENERATED_CI_FAILURE_NOTIFIER_111 -->"
    mock_mr1.notes.list.return_value = [mock_note1]

    # MR2: CI passed, no notification needed
    mock_mr2 = MagicMock()
    mock_mr2.title = "MR 2"
    mock_mr2.iid = 2
    mock_pipeline2 = MagicMock()
    mock_pipeline2.status = 'success'
    mock_pipeline2.id = 222
    mock_mr2.pipelines.list.return_value = [mock_pipeline2]
    mock_mr2.notes.list.return_value = []

    # MR3: CI failed, not notified
    mock_mr3 = MagicMock()
    mock_mr3.title = "MR 3"
    mock_mr3.iid = 3
    mock_pipeline3 = MagicMock()
    mock_pipeline3.status = 'failed'
    mock_pipeline3.id = 999
    mock_mr3.pipelines.list.return_value = [mock_pipeline3]
    mock_mr3.notes.list.return_value = []

    # MR4: No pipeline
    mock_mr4 = MagicMock()
    mock_mr4.title = "MR 4"
    mock_mr4.iid = 4
    mock_mr4.pipelines.list.return_value = []

    mock_project.mergerequests.list.return_value = [mock_mr1, mock_mr2, mock_mr3, mock_mr4]

    result = await gitlab_mr_cicd_failure_notifier_task()
    assert result == "GitLab MR CI/CD failure notifier task completed"

    # Note should only be added for MR3
    mock_gl_instance.create_mr_note.assert_called_once_with("proj1", 3, "Please fix your CI! <!-- AUTO_GENERATED_CI_FAILURE_NOTIFIER_999 -->")

    # LLM should be invoked once
    mock_llm_instance.ainvoke.assert_called_once()
    assert "999" in mock_llm_instance.ainvoke.call_args[0][0]
