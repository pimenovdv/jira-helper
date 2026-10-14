import pytest
from unittest.mock import MagicMock, call

@pytest.mark.asyncio
async def test_gitlab_mr_missing_milestone_warning_task_warns(mocker):
    from app.tasks import gitlab_mr_missing_milestone_warning_task

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, d="": "TEST-PROJ" if k == "GITLAB_TRACKED_PROJECTS" else d
    mocker.patch("app.tasks.settings", mock_settings)
    mocker.patch("app.clients.settings", mock_settings)

    mock_gitlab_cls = mocker.patch("app.clients.gitlab_client.GitLabClient")
    mock_gitlab = mock_gitlab_cls.return_value

    class MockNote:
        def __init__(self, body):
            self.body = body

    class MockMR:
        def __init__(self, iid, milestone, author, notes_list):
            self.iid = iid
            self.milestone = milestone
            self.author = author
            self.notes = mocker.MagicMock()
            self.notes.list.return_value = notes_list

    mock_mr_no_milestone = MockMR(
        iid=123,
        milestone=None,
        author={"id": 1, "username": "test_user"},
        notes_list=[MockNote(body="Some other comment")]
    )

    mock_mr_with_milestone = MockMR(
        iid=124,
        milestone={"id": 1, "title": "v1.0"},
        author={"id": 1, "username": "test_user"},
        notes_list=[]
    )

    # To fix pytest-mock MagicMock getattr returning MagicMocks
    # which causes isinstance checks inside tasks.py to misbehave,
    # we just provide the return value explicitly as a list
    mock_gitlab.get_project_merge_requests.return_value = [mock_mr_no_milestone, mock_mr_with_milestone]

    res = await gitlab_mr_missing_milestone_warning_task()

    assert res == "GitLab MR missing milestone warning task completed: warned 1 MRs."
    mock_gitlab.create_mr_note.assert_called_once()
    args, _ = mock_gitlab.create_mr_note.call_args
    assert args[0] == "TEST-PROJ"
    assert args[1] == 123
    assert "<!-- AUTO_GENERATED_MISSING_MILESTONE_WARNING -->" in args[2]
    assert "@test_user" in args[2]


@pytest.mark.asyncio
async def test_gitlab_mr_missing_milestone_warning_task_already_warned(mocker):
    from app.tasks import gitlab_mr_missing_milestone_warning_task

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, d="": "TEST-PROJ" if k == "GITLAB_TRACKED_PROJECTS" else d
    mocker.patch("app.tasks.settings", mock_settings)
    mocker.patch("app.clients.settings", mock_settings)

    mock_gitlab_cls = mocker.patch("app.clients.gitlab_client.GitLabClient")
    mock_gitlab = mock_gitlab_cls.return_value

    class MockNote:
        def __init__(self, body):
            self.body = body

    class MockMR:
        def __init__(self, iid, milestone, author, notes_list):
            self.iid = iid
            self.milestone = milestone
            self.author = author
            self.notes = mocker.MagicMock()
            self.notes.list.return_value = notes_list

    mock_mr_no_milestone = MockMR(
        iid=123,
        milestone=None,
        author={"id": 1, "username": "test_user"},
        notes_list=[MockNote(body="<!-- AUTO_GENERATED_MISSING_MILESTONE_WARNING -->")]
    )

    mock_gitlab.get_project_merge_requests.return_value = [mock_mr_no_milestone]

    res = await gitlab_mr_missing_milestone_warning_task()

    assert res == "GitLab MR missing milestone warning task completed: warned 0 MRs."
    mock_gitlab.create_mr_note.assert_not_called()
