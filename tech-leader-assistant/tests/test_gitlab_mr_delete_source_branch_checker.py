import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.tasks import gitlab_mr_delete_source_branch_checker_task

@pytest.fixture
def mock_gitlab_client(mocker):
    client = MagicMock()
    mocker.patch('app.tasks.GitLabClient', return_value=client)
    return client

@pytest.fixture
def mock_settings(mocker):
    settings = MagicMock()
    settings.get.side_effect = lambda key, default="": {
        "OPENAI_API_KEY": "test_key",
        "GITLAB_TRACKED_PROJECTS": "test_project"
    }.get(key, default)
    mocker.patch('app.tasks.settings', settings)
    return settings

@pytest.fixture
def mock_llm(mocker):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="Please delete the source branch."))
    mocker.patch('app.tasks.ChatOpenAI', return_value=llm)
    return llm

@pytest.mark.asyncio
async def test_gitlab_mr_delete_source_branch_checker_task_no_api_key(mocker):
    settings = MagicMock()
    settings.get.return_value = ""
    mocker.patch('app.tasks.settings', settings)

    result = await gitlab_mr_delete_source_branch_checker_task()
    assert result == "GitLab MR delete source branch checker task skipped (no OpenAI API key)"

@pytest.mark.asyncio
async def test_gitlab_mr_delete_source_branch_checker_task_flag_false_adds_comment(
    mock_gitlab_client, mock_settings, mock_llm
):
    project = MagicMock()
    mock_gitlab_client.get_project.return_value = project

    mr = MagicMock()
    mr.iid = 1
    mr.force_remove_source_branch = False
    mr.author = {"username": "testuser"}

    # Mock notes
    mr.notes.list.return_value = []

    project.mergerequests.list.return_value = [mr]

    await gitlab_mr_delete_source_branch_checker_task()

    # Verify LLM was called
    mock_llm.ainvoke.assert_called_once()

    # Verify comment was posted
    mock_gitlab_client.create_mr_note.assert_called_once_with(
        "test_project", 1, "Please delete the source branch.\n\n<!-- AUTO_GENERATED_DELETE_SOURCE_BRANCH -->"
    )

@pytest.mark.asyncio
async def test_gitlab_mr_delete_source_branch_checker_task_flag_true_skips(
    mock_gitlab_client, mock_settings, mock_llm
):
    project = MagicMock()
    mock_gitlab_client.get_project.return_value = project

    mr = MagicMock()
    mr.iid = 1
    mr.force_remove_source_branch = True
    project.mergerequests.list.return_value = [mr]

    await gitlab_mr_delete_source_branch_checker_task()

    # Verify no comment was posted
    mock_gitlab_client.create_mr_note.assert_not_called()
    mock_llm.ainvoke.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_delete_source_branch_checker_task_already_reminded_skips(
    mock_gitlab_client, mock_settings, mock_llm
):
    project = MagicMock()
    mock_gitlab_client.get_project.return_value = project

    mr = MagicMock()
    mr.iid = 1
    mr.force_remove_source_branch = False

    note = MagicMock()
    note.body = "Some text <!-- AUTO_GENERATED_DELETE_SOURCE_BRANCH -->"
    mr.notes.list.return_value = [note]

    project.mergerequests.list.return_value = [mr]

    await gitlab_mr_delete_source_branch_checker_task()

    # Verify no comment was posted
    mock_gitlab_client.create_mr_note.assert_not_called()
    mock_llm.ainvoke.assert_not_called()
