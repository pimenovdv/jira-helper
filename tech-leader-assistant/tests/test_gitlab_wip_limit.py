import pytest
from unittest.mock import MagicMock, AsyncMock
from app.tasks import gitlab_mr_wip_limit_reminder_task

from app.tasks import settings

@pytest.mark.asyncio
async def test_gitlab_wip_limit_reminder_no_projects(mocker):
    settings.set('GITLAB_TRACKED_PROJECTS', "")
    mocker.patch('app.tasks.GitLabClient')

    result = await gitlab_mr_wip_limit_reminder_task()

    assert result == "No projects tracked"

@pytest.mark.asyncio
async def test_gitlab_wip_limit_reminder_under_limit(mocker):
    settings.set('GITLAB_TRACKED_PROJECTS', "proj-1")
    mock_gitlab = MagicMock()

    mocker.patch('app.tasks.GitLabClient', return_value=mock_gitlab)

    mock_mr1 = MagicMock()
    mock_mr1.author = {'username': 'user1'}
    mock_mr2 = MagicMock()
    mock_mr2.author = {'username': 'user1'}

    mock_gitlab.get_project_merge_requests.return_value = [mock_mr1, mock_mr2]

    result = await gitlab_mr_wip_limit_reminder_task()

    assert result == "GitLab MR WIP limit reminder task completed"
    mock_gitlab.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_wip_limit_reminder_over_limit_success(mocker):
    settings.set('GITLAB_TRACKED_PROJECTS', "proj-1")
    mock_gitlab = MagicMock()
    mocker.patch('app.tasks.GitLabClient', return_value=mock_gitlab)

    mrs = []
    for i in range(4):
        mr = MagicMock()
        mr.author = {'username': 'user1'}
        mr.created_at = f"2023-10-0{i+1}T10:00:00Z"
        mr.iid = i + 1
        mr.notes.list.return_value = []
        mrs.append(mr)

    mock_gitlab.get_project_merge_requests.return_value = mrs

    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "WIP limit exceeded message."
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    mocker.patch('app.tasks.ChatOpenAI', return_value=mock_llm)

    result = await gitlab_mr_wip_limit_reminder_task()

    assert result == "GitLab MR WIP limit reminder task completed"
    mock_gitlab.create_mr_note.assert_called_once_with(
        "proj-1",
        4,
        "WIP limit exceeded message.\n\n<!-- AUTO_GENERATED_WIP_LIMIT_REMINDER -->"
    )

@pytest.mark.asyncio
async def test_gitlab_wip_limit_reminder_already_notified(mocker):
    settings.set('GITLAB_TRACKED_PROJECTS', "proj-1")
    mock_gitlab = MagicMock()
    mocker.patch('app.tasks.GitLabClient', return_value=mock_gitlab)

    mrs = []
    for i in range(4):
        mr = MagicMock()
        mr.author = {'username': 'user1'}
        mr.created_at = f"2023-10-0{i+1}T10:00:00Z"
        mr.iid = i + 1

        mock_note = MagicMock()
        if i == 3: # Most recent MR
            mock_note.body = "Some comment\n\n<!-- AUTO_GENERATED_WIP_LIMIT_REMINDER -->"
        else:
            mock_note.body = "Regular comment"

        mr.notes.list.return_value = [mock_note]
        mrs.append(mr)

    mock_gitlab.get_project_merge_requests.return_value = mrs
    mocker.patch('app.tasks.ChatOpenAI', return_value=MagicMock())

    result = await gitlab_mr_wip_limit_reminder_task()

    assert result == "GitLab MR WIP limit reminder task completed"
    mock_gitlab.create_mr_note.assert_not_called()
