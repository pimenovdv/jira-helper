import pytest
from unittest.mock import MagicMock
from app.tasks import confluence_stale_page_warning_task

@pytest.mark.asyncio
async def test_confluence_stale_page_warning_task_no_spaces(mocker):
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = ""
    mock_logger = mocker.patch("app.tasks.logger")

    await confluence_stale_page_warning_task()

    mock_logger.warning.assert_called_once_with("No Confluence spaces configured for tracking.")

@pytest.mark.asyncio
async def test_confluence_stale_page_warning_task_adds_comment(mocker):
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = "SPACE1"

    mock_confluence_client_cls = mocker.patch("app.tasks.ConfluenceClient")
    mock_confluence_client = mock_confluence_client_cls.return_value

    # Mock search results
    mock_confluence_client.search_cql.return_value = {
        "results": [
            {"content": {"id": "12345"}}
        ]
    }

    mock_client_client = MagicMock()
    mock_confluence_client.client = mock_client_client

    mock_client_client.get_page_by_id.return_value = {
        "history": {
            "lastUpdated": {
                "by": {
                    "accountId": "user123"
                }
            }
        }
    }

    # Mock page comments (no previous warning)
    mock_client_client.get_page_comments.return_value = {
        "results": [
            {
                "body": {
                    "storage": {
                        "value": "Some regular comment"
                    }
                }
            }
        ]
    }

    await confluence_stale_page_warning_task()

    mock_confluence_client.search_cql.assert_called_once_with('space="SPACE1" and lastmodified < now("-52w")', start=0, limit=100)
    mock_client_client.get_page_comments.assert_called_once_with("12345", expand='body.storage')
    mock_client_client.add_comment.assert_called_once_with(
        "12345",
        ("<!-- AUTO_GENERATED_CONFLUENCE_STALE_PAGE_WARNING -->"
        "[~accountid:user123] This page hasn't been updated in over a year. "
        "Please review if it is still relevant.")
    )

@pytest.mark.asyncio
async def test_confluence_stale_page_warning_task_already_warned(mocker):
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = "SPACE1"

    mock_confluence_client_cls = mocker.patch("app.tasks.ConfluenceClient")
    mock_confluence_client = mock_confluence_client_cls.return_value

    # Mock search results
    mock_confluence_client.search_cql.return_value = {
        "results": [
            {"content": {"id": "12345"}}
        ]
    }

    mock_client_client = MagicMock()
    mock_confluence_client.client = mock_client_client

    mock_client_client.get_page_by_id.return_value = {
        "history": {
            "lastUpdated": {
                "by": {
                    "accountId": "user123"
                }
            }
        }
    }

    # Mock page comments (previous warning exists)
    mock_client_client.get_page_comments.return_value = {
        "results": [
            {
                "body": {
                    "storage": {
                        "value": ("<!-- AUTO_GENERATED_CONFLUENCE_STALE_PAGE_WARNING -->"
        "[~accountid:user123] This page hasn't been updated in over a year. "
        "Please review if it is still relevant.")
                    }
                }
            }
        ]
    }

    await confluence_stale_page_warning_task()

    mock_client_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_confluence_stale_page_warning_task_pagination_empty(mocker):
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = "SPACE1"

    mock_confluence_client_cls = mocker.patch("app.tasks.ConfluenceClient")
    mock_confluence_client = mock_confluence_client_cls.return_value

    # Mock search results to be empty
    mock_confluence_client.search_cql.return_value = {
        "results": []
    }

    await confluence_stale_page_warning_task()

    mock_confluence_client.search_cql.assert_called_once_with('space="SPACE1" and lastmodified < now("-52w")', start=0, limit=100)

@pytest.mark.asyncio
async def test_confluence_stale_page_warning_task_add_comment_exception(mocker):
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = "SPACE1"
    mock_logger = mocker.patch("app.tasks.logger")

    mock_confluence_client_cls = mocker.patch("app.tasks.ConfluenceClient")
    mock_confluence_client = mock_confluence_client_cls.return_value

    # Mock search results
    mock_confluence_client.search_cql.return_value = {
        "results": [
            {"content": {"id": "12345"}}
        ]
    }

    mock_client_client = MagicMock()
    mock_confluence_client.client = mock_client_client

    mock_client_client.get_page_by_id.return_value = {
        "history": {
            "lastUpdated": {
                "by": {
                    "accountId": "user123"
                }
            }
        }
    }
    mock_client_client.get_page_comments.return_value = {"results": []}
    mock_client_client.add_comment.side_effect = Exception("API Error")

    await confluence_stale_page_warning_task()

    mock_client_client.add_comment.assert_called_once()
    mock_logger.error.assert_any_call("Failed to add comment to page 12345: API Error")

@pytest.mark.asyncio
async def test_confluence_stale_page_warning_task_top_level_exception(mocker):
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.side_effect = Exception("Settings Error")
    mock_logger = mocker.patch("app.tasks.logger")

    await confluence_stale_page_warning_task()

    mock_logger.error.assert_called_once_with("Error in confluence_stale_page_warning_task: Settings Error")

@pytest.mark.asyncio
async def test_confluence_stale_page_warning_task_no_account_id(mocker):
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.return_value = "SPACE1"

    mock_confluence_client_cls = mocker.patch("app.tasks.ConfluenceClient")
    mock_confluence_client = mock_confluence_client_cls.return_value

    # Mock search results for two pages to cover start += limit
    pages_batch_1 = [{"content": {"id": f"page_{i}"}} for i in range(100)]
    mock_confluence_client.search_cql.side_effect = [
        {"results": pages_batch_1},
        {"results": []}
    ]

    mock_client_client = MagicMock()
    mock_confluence_client.client = mock_client_client

    mock_client_client.get_page_by_id.return_value = {}

    mock_client_client.get_page_comments.return_value = {"results": []}

    await confluence_stale_page_warning_task()

    assert mock_client_client.add_comment.call_count == 100
    assert mock_confluence_client.search_cql.call_count == 2
