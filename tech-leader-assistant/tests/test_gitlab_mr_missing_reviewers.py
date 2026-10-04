import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_missing_reviewers_notifier_task

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch("app.tasks.settings")
    mock.get.side_effect = lambda k, d="": "proj1,proj2" if k == "GITLAB_TRACKED_PROJECTS" else d
    return mock

@pytest.fixture
def mock_gitlab_client(mocker):
    mock = MagicMock()
    mocker.patch("app.tasks.GitLabClient", return_value=mock)
    return mock

@pytest.mark.asyncio
async def test_gitlab_mr_missing_reviewers_notifier_adds_comment_when_missing(mock_settings, mock_gitlab_client):
    # Setup mock MRs
    # MR 1: Has reviewers
    mr1 = MagicMock()
    mr1.iid = 1
    mr1.reviewers = [{"username": "user1"}]

    # MR 2: Missing reviewers, no prior comment
    mr2 = MagicMock()
    mr2.iid = 2
    mr2.reviewers = []
    mr2.author = {"username": "author2"}
    note2 = MagicMock()
    note2.body = "Just a regular comment"
    mr2.notes.list.return_value = [note2]

    # MR 3: Missing reviewers, but already has automated comment
    mr3 = MagicMock()
    mr3.iid = 3
    mr3.reviewers = []
    mr3.author = {"username": "author3"}
    note3 = MagicMock()
    note3.body = "<!-- AUTO_GENERATED_MISSING_REVIEWERS_WARNING -->\nPlease add reviewers."
    mr3.notes.list.return_value = [note3]

    mock_gitlab_client.get_merge_requests.side_effect = lambda proj, **kwargs: [mr1, mr2, mr3] if proj == "proj1" else []

    # Run task
    result = await gitlab_mr_missing_reviewers_notifier_task()

    assert result == "GitLab MR missing reviewers notifier task completed."

    # Assert get_merge_requests was called for both projects
    assert mock_gitlab_client.get_merge_requests.call_count == 2
    mock_gitlab_client.get_merge_requests.assert_any_call("proj1", state="opened")
    mock_gitlab_client.get_merge_requests.assert_any_call("proj2", state="opened")

    # Assert comment was added ONLY to MR 2
    mock_gitlab_client.create_mr_note.assert_called_once()
    args, kwargs = mock_gitlab_client.create_mr_note.call_args
    assert args[0] == "proj1"
    assert args[1] == 2
    assert "<!-- AUTO_GENERATED_MISSING_REVIEWERS_WARNING -->" in args[2]
    assert "@author2" in args[2]

@pytest.mark.asyncio
async def test_gitlab_mr_missing_reviewers_notifier_handles_errors(mock_settings, mock_gitlab_client, caplog):
    # Setup error
    mock_gitlab_client.get_merge_requests.side_effect = Exception("API Error")

    result = await gitlab_mr_missing_reviewers_notifier_task()

    assert result == "GitLab MR missing reviewers notifier task completed."
    assert "Error processing missing reviewers notifier for project proj1" in caplog.text
    assert "Error processing missing reviewers notifier for project proj2" in caplog.text
