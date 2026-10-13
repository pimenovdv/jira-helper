import pytest
from unittest.mock import MagicMock, call
from app.tasks import gitlab_mr_reviewer_self_assignment_warning_task

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.tasks.settings")
    mock.get.return_value = "project1"
    return mock

@pytest.fixture
def mock_gitlab_client(mocker):
    mock = mocker.patch("app.tasks.GitLabClient")
    instance = mock.return_value
    return instance

@pytest.mark.asyncio
async def test_gitlab_mr_reviewer_self_assignment_warning_task_adds_warning(mock_gitlab_client, mock_settings):
    mr_mock = MagicMock()
    mr_mock.iid = 1
    mr_mock.author = {'id': 100, 'username': 'test_user'}
    mr_mock.reviewers = [{'id': 100, 'username': 'test_user'}]

    note_mock = MagicMock()
    note_mock.body = "some unrelated note"
    mr_mock.notes.list.return_value = [note_mock]

    mock_gitlab_client.get_merge_requests.return_value = [mr_mock]

    await gitlab_mr_reviewer_self_assignment_warning_task()

    mock_gitlab_client.get_merge_requests.assert_called_once_with("project1", state="opened")
    mr_mock.notes.create.assert_called_once()
    args, kwargs = mr_mock.notes.create.call_args
    # Since it's called with `mr.notes.create({'body': comment_body})`
    # args[0] is the dictionary `{'body': comment_body}`
    assert "<!-- AUTO_GENERATED_SELF_ASSIGNMENT_WARNING -->" in args[0]['body']
    assert "@test_user" in args[0]['body']

@pytest.mark.asyncio
async def test_gitlab_mr_reviewer_self_assignment_warning_task_skips_if_already_warned(mock_gitlab_client, mock_settings):
    mr_mock = MagicMock()
    mr_mock.iid = 2
    mr_mock.author = {'id': 100, 'username': 'test_user'}
    mr_mock.reviewers = [{'id': 100, 'username': 'test_user'}]

    note_mock = MagicMock()
    note_mock.body = "<!-- AUTO_GENERATED_SELF_ASSIGNMENT_WARNING -->\nAlready warned."
    mr_mock.notes.list.return_value = [note_mock]

    mock_gitlab_client.get_merge_requests.return_value = [mr_mock]

    await gitlab_mr_reviewer_self_assignment_warning_task()

    mr_mock.notes.create.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_reviewer_self_assignment_warning_task_skips_if_different_reviewer(mock_gitlab_client, mock_settings):
    mr_mock = MagicMock()
    mr_mock.iid = 3
    mr_mock.author = {'id': 100, 'username': 'test_user'}
    mr_mock.reviewers = [{'id': 101, 'username': 'other_user'}]

    mock_gitlab_client.get_merge_requests.return_value = [mr_mock]

    await gitlab_mr_reviewer_self_assignment_warning_task()

    mr_mock.notes.create.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_reviewer_self_assignment_warning_task_skips_if_no_reviewer(mock_gitlab_client, mock_settings):
    mr_mock = MagicMock()
    mr_mock.iid = 4
    mr_mock.author = {'id': 100, 'username': 'test_user'}
    mr_mock.reviewers = []

    mock_gitlab_client.get_merge_requests.return_value = [mr_mock]

    await gitlab_mr_reviewer_self_assignment_warning_task()

    mr_mock.notes.create.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_mr_reviewer_self_assignment_warning_task_skips_if_multiple_reviewers(mock_gitlab_client, mock_settings):
    mr_mock = MagicMock()
    mr_mock.iid = 5
    mr_mock.author = {'id': 100, 'username': 'test_user'}
    mr_mock.reviewers = [{'id': 100, 'username': 'test_user'}, {'id': 101, 'username': 'other_user'}]

    mock_gitlab_client.get_merge_requests.return_value = [mr_mock]

    await gitlab_mr_reviewer_self_assignment_warning_task()

    mr_mock.notes.create.assert_not_called()
