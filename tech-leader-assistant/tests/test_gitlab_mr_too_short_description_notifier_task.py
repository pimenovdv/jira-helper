import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_too_short_description_notifier_task

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
async def test_gitlab_mr_too_short_description_notifier_adds_comment_when_too_short(mock_settings, mock_gitlab_client):
    # Setup mock MRs
    # MR 1: Long description
    mr1 = MagicMock()
    mr1.iid = 1
    mr1.description = "This is a very long description that is over 30 characters long."
    mr1.author = {"username": "user1"}

    # MR 2: Short description, no prior comment
    mr2 = MagicMock()
    mr2.iid = 2
    mr2.description = "Short desc"
    mr2.author = {"username": "author2"}
    note2 = MagicMock()
    note2.body = "Just a regular comment"
    mr2.notes.list.return_value = [note2]

    # MR 3: Short description, but already has automated comment
    mr3 = MagicMock()
    mr3.iid = 3
    mr3.description = "Short"
    mr3.author = {"username": "author3"}
    note3 = MagicMock()
    note3.body = "<!-- AUTO_GENERATED_TOO_SHORT_DESCRIPTION_WARNING -->\nPlease add a better description."
    mr3.notes.list.return_value = [note3]

    # MR 4: None description
    mr4 = MagicMock()
    mr4.iid = 4
    mr4.description = None
    mr4.author = {"username": "author4"}
    mr4.notes.list.return_value = []

    mock_gitlab_client.get_merge_requests.side_effect = lambda proj, **kwargs: [mr1, mr2, mr3, mr4] if proj == "proj1" else []

    # Run task
    result = await gitlab_mr_too_short_description_notifier_task()

    assert result == "GitLab MR too short description notifier task completed."

    # Assert get_merge_requests was called for both projects
    assert mock_gitlab_client.get_merge_requests.call_count == 2
    mock_gitlab_client.get_merge_requests.assert_any_call("proj1", state="opened")
    mock_gitlab_client.get_merge_requests.assert_any_call("proj2", state="opened")

    # Assert comment was added to MR 2 and MR 4
    assert mock_gitlab_client.create_mr_note.call_count == 2

    args2, kwargs2 = mock_gitlab_client.create_mr_note.call_args_list[0]
    assert args2[0] == "proj1"
    assert args2[1] == 2
    assert "<!-- AUTO_GENERATED_TOO_SHORT_DESCRIPTION_WARNING -->" in args2[2]
    assert "@author2" in args2[2]

    args4, kwargs4 = mock_gitlab_client.create_mr_note.call_args_list[1]
    assert args4[0] == "proj1"
    assert args4[1] == 4
    assert "<!-- AUTO_GENERATED_TOO_SHORT_DESCRIPTION_WARNING -->" in args4[2]
    assert "@author4" in args4[2]

@pytest.mark.asyncio
async def test_gitlab_mr_too_short_description_notifier_handles_errors(mock_settings, mock_gitlab_client, caplog):
    # Setup error
    mock_gitlab_client.get_merge_requests.side_effect = Exception("API Error")

    result = await gitlab_mr_too_short_description_notifier_task()

    assert result == "GitLab MR too short description notifier task completed."
    assert "Error processing too short description notifier for project proj1" in caplog.text
    assert "Error processing too short description notifier for project proj2" in caplog.text
