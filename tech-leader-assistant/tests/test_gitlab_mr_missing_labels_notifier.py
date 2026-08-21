import pytest
from unittest.mock import MagicMock, call
import asyncio
from app.tasks import gitlab_mr_missing_labels_notifier_task
from langchain_core.messages import HumanMessage

@pytest.mark.asyncio
async def test_gitlab_mr_missing_labels_notifier_success(mocker):
    # Setup mocks
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.side_effect = lambda k, d="": "dummy_key" if k == "OPENAI_API_KEY" else "proj1" if k == "GITLAB_TRACKED_PROJECTS" else d

    mock_llm_instance = MagicMock()
    mock_llm_instance.ainvoke = mocker.AsyncMock(return_value=MagicMock(content="Пожалуйста, добавьте метки."))
    mocker.patch("app.tasks.ChatOpenAI", return_value=mock_llm_instance)

    mock_gitlab_client_instance = MagicMock()
    mock_gitlab_client_instance.client.projects.get.return_value = MagicMock()
    mock_project = mock_gitlab_client_instance.client.projects.get.return_value

    mock_mr = MagicMock()
    mock_mr.iid = 123
    mock_mr.labels = []
    mock_mr.author = {"username": "testuser"}

    mock_note = MagicMock()
    mock_note.body = "Some regular comment"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project.mergerequests.list.return_value = [mock_mr]
    mocker.patch("app.tasks.GitLabClient", return_value=mock_gitlab_client_instance)

    # Execute
    result = await gitlab_mr_missing_labels_notifier_task()

    # Assert
    assert result == "GitLab MR missing labels notifier task completed."
    mock_gitlab_client_instance.create_mr_note.assert_called_once()
    args, _ = mock_gitlab_client_instance.create_mr_note.call_args
    assert args[0] == "proj1"
    assert args[1] == 123
    assert "Пожалуйста, добавьте метки." in args[2]
    assert "<!-- AUTO_GENERATED_GITLAB_MISSING_LABELS_REMINDER -->" in args[2]

@pytest.mark.asyncio
async def test_gitlab_mr_missing_labels_notifier_has_labels(mocker):
    # Setup mocks
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.side_effect = lambda k, d="": "dummy_key" if k == "OPENAI_API_KEY" else "proj1" if k == "GITLAB_TRACKED_PROJECTS" else d

    mock_llm_instance = MagicMock()
    mocker.patch("app.tasks.ChatOpenAI", return_value=mock_llm_instance)

    mock_gitlab_client_instance = MagicMock()
    mock_gitlab_client_instance.client.projects.get.return_value = MagicMock()
    mock_project = mock_gitlab_client_instance.client.projects.get.return_value

    mock_mr = MagicMock()
    mock_mr.iid = 123
    mock_mr.labels = ["bug"]

    mock_project.mergerequests.list.return_value = [mock_mr]
    mocker.patch("app.tasks.GitLabClient", return_value=mock_gitlab_client_instance)

    # Execute
    result = await gitlab_mr_missing_labels_notifier_task()

    # Assert
    assert result == "GitLab MR missing labels notifier task completed."
    mock_gitlab_client_instance.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_labels_notifier_already_notified(mocker):
    # Setup mocks
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.side_effect = lambda k, d="": "dummy_key" if k == "OPENAI_API_KEY" else "proj1" if k == "GITLAB_TRACKED_PROJECTS" else d

    mock_llm_instance = MagicMock()
    mocker.patch("app.tasks.ChatOpenAI", return_value=mock_llm_instance)

    mock_gitlab_client_instance = MagicMock()
    mock_gitlab_client_instance.client.projects.get.return_value = MagicMock()
    mock_project = mock_gitlab_client_instance.client.projects.get.return_value

    mock_mr = MagicMock()
    mock_mr.iid = 123
    mock_mr.labels = []

    mock_note = MagicMock()
    mock_note.body = "Пожалуйста, добавьте метки. \n\n<!-- AUTO_GENERATED_GITLAB_MISSING_LABELS_REMINDER -->"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project.mergerequests.list.return_value = [mock_mr]
    mocker.patch("app.tasks.GitLabClient", return_value=mock_gitlab_client_instance)

    # Execute
    result = await gitlab_mr_missing_labels_notifier_task()

    # Assert
    assert result == "GitLab MR missing labels notifier task completed."
    mock_gitlab_client_instance.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_missing_labels_notifier_no_api_key(mocker):
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = ""

    result = await gitlab_mr_missing_labels_notifier_task()

    assert result == "GitLab MR missing labels notifier task skipped (no OpenAI API key)"
