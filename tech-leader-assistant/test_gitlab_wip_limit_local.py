import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

async def run_test():
    from app.tasks import settings, gitlab_mr_wip_limit_reminder_task
    settings.set('GITLAB_TRACKED_PROJECTS', "proj-1")

    with patch('app.tasks.GitLabClient') as mock_gitlab_cls:
        mock_gitlab = MagicMock()
        mock_gitlab_cls.return_value = mock_gitlab

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

        with patch('app.tasks.ChatOpenAI', return_value=mock_llm):
            with patch('app.tasks.logger.info') as mock_info:
                with patch('app.tasks.logger.error') as mock_error:
                    res = await gitlab_mr_wip_limit_reminder_task()
                    print(res)
                    print("Errors:", mock_error.call_args_list)
                    print("Info:", mock_info.call_args_list)
                    print("Create:", mock_gitlab.create_mr_note.call_args_list)

asyncio.run(run_test())
