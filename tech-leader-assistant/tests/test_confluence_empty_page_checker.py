import pytest
from app.tasks import confluence_empty_page_checker_task

@pytest.fixture
def mock_settings():
    from app.clients import settings
    old_val = settings.get("CONFLUENCE_TRACKED_SPACES")
    settings.set("CONFLUENCE_TRACKED_SPACES", "SPACE1")
    yield settings
    settings.set("CONFLUENCE_TRACKED_SPACES", old_val)

@pytest.fixture
def mock_confluence_client(mocker):
    mock_client_class = mocker.patch("app.clients.confluence_client.ConfluenceClient")
    mock_instance = mock_client_class.return_value
    return mock_instance

@pytest.mark.asyncio
async def test_confluence_empty_page_checker_task_enough_content(mock_confluence_client, mock_settings):
    # Setup mock data
    mock_confluence_client.client.get_all_pages_from_space.return_value = {
        "results": [
            {
                "id": "123",
                "body": {"storage": {"value": "<p>This is a page with enough content to pass the 50 characters threshold. Here is more text so it is definitively longer.</p>"}},
                "history": {"lastUpdated": {"by": {"accountId": "user1"}}}
            }
        ]
    }

    result = await confluence_empty_page_checker_task()

    assert result == "Confluence empty page checker task completed"
    mock_confluence_client.client.get_page_comments.assert_not_called()
    mock_confluence_client.client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_confluence_empty_page_checker_task_empty_page_no_comment(mock_confluence_client, mock_settings):
    mock_confluence_client.client.get_all_pages_from_space.return_value = {
        "results": [
            {
                "id": "124",
                "body": {"storage": {"value": "<p>Short</p>"}},
                "history": {"lastUpdated": {"by": {"accountId": "user2"}}}
            }
        ]
    }
    mock_confluence_client.client.get_page_comments.return_value = {"results": []}

    result = await confluence_empty_page_checker_task()

    assert result == "Confluence empty page checker task completed"
    mock_confluence_client.client.get_page_comments.assert_called_with("124", expand="body.storage")
    assert mock_confluence_client.client.get_page_comments.call_count == 1
    mock_confluence_client.client.add_comment.assert_called_once()

    call_args = mock_confluence_client.client.add_comment.call_args[0]
    assert call_args[0] == "124"
    assert "AUTO_GENERATED_EMPTY_PAGE_WARNING" in call_args[1]
    assert '<ac:link><ri:user ri:account-id="user2"/></ac:link>' in call_args[1]

@pytest.mark.asyncio
async def test_confluence_empty_page_checker_task_already_commented(mock_confluence_client, mock_settings):
    mock_confluence_client.client.get_all_pages_from_space.return_value = {
        "results": [
            {
                "id": "125",
                "body": {"storage": {"value": "<p>Too short</p>"}},
                "history": {"lastUpdated": {"by": {"accountId": "user3"}}}
            }
        ]
    }
    mock_confluence_client.client.get_page_comments.return_value = {
        "results": [
            {
                "body": {
                    "storage": {
                        "value": "Some comment <!-- AUTO_GENERATED_EMPTY_PAGE_WARNING --> and more"
                    }
                }
            }
        ]
    }

    result = await confluence_empty_page_checker_task()

    assert result == "Confluence empty page checker task completed"
    mock_confluence_client.client.get_page_comments.assert_called_with("125", expand="body.storage")
    assert mock_confluence_client.client.get_page_comments.call_count == 1
    mock_confluence_client.client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_confluence_empty_page_checker_task_exception_handling(mock_confluence_client, mock_settings):
    mock_confluence_client.client.get_all_pages_from_space.side_effect = Exception("API Error")

    result = await confluence_empty_page_checker_task()

    assert result == "Confluence empty page checker task completed"
