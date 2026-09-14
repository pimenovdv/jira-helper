import pytest
from unittest.mock import MagicMock
from app.tasks import confluence_stale_documentation_archiver_task
from app import tasks
from datetime import datetime, timezone, timedelta

@pytest.fixture
def mock_settings(mocker):
    # Mock both direct app.tasks.settings and app.clients.confluence_client.settings if needed, but since we use app.clients.settings in tasks.py:
    # In tasks.py: from app.clients import settings
    # Let's mock tasks.settings
    mock = mocker.patch("app.clients.settings")
    def mock_get(key, default=""):
        if key == "CONFLUENCE_TRACKED_SPACES": return "SPACE1"
        return default
    mock.get.side_effect = mock_get
    return mock

@pytest.fixture
def mock_confluence_client(mocker):
    # Mock ConfluenceClient at the tasks module level
    mock_cls = mocker.patch("app.clients.confluence_client.ConfluenceClient")
    mock_instance = mock_cls.return_value
    mock_instance.client = MagicMock()
    return mock_instance

@pytest.mark.asyncio
async def test_no_spaces_configured(mocker):
    mock = mocker.patch("app.clients.settings")
    mock.get.return_value = ""
    res = await confluence_stale_documentation_archiver_task()
    assert "skipped" in res
    assert "no spaces configured" in res

@pytest.mark.asyncio
async def test_stale_page_archived(mock_settings, mock_confluence_client):
    old_date = (datetime.now(timezone.utc) - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # 1. Page fetching
    mock_confluence_client.client.get_all_pages_from_space.return_value = {
        "results": [
            {
                "id": "123",
                "title": "Old Draft Page",
                "version": {"when": old_date, "number": 1},
                "body": {"storage": {"value": "<p>Content</p>"}},
                "history": {"lastUpdated": {"by": {"accountId": "account123"}}}
            }
        ]
    }

    # 2. Labels fetching
    mock_confluence_client.client.get_page_labels.return_value = {
        "results": [{"name": "draft"}]
    }

    res = await confluence_stale_documentation_archiver_task()

    assert "Archived 1 pages" in res

    # Verify label added
    mock_confluence_client.client.set_page_label.assert_called_once_with("123", "archived")

    # Verify page title updated
    mock_confluence_client.client.update_page.assert_called_once_with(
        "123", "[ARCHIVED] Old Draft Page", "<p>Content</p>",
        parent_id=None, type='page', representation='storage',
        minor_edit=False, version_comment='Auto-archived stale documentation'
    )

    # Verify comment added with tag
    mock_confluence_client.client.add_comment.assert_called_once()
    call_args = mock_confluence_client.client.add_comment.call_args[0]
    assert call_args[0] == "123"
    assert "[~accountid:account123]" in call_args[1]
    assert "<!-- AUTO_GENERATED_CONFLUENCE_ARCHIVER -->" in call_args[1]

@pytest.mark.asyncio
async def test_recent_page_ignored(mock_settings, mock_confluence_client):
    recent_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    mock_confluence_client.client.get_all_pages_from_space.return_value = {
        "results": [
            {
                "id": "123",
                "title": "Recent Draft Page",
                "version": {"when": recent_date, "number": 1},
            }
        ]
    }

    res = await confluence_stale_documentation_archiver_task()

    assert "Archived 0 pages" in res
    mock_confluence_client.client.get_page_labels.assert_not_called()
    mock_confluence_client.client.set_page_label.assert_not_called()

@pytest.mark.asyncio
async def test_missing_label_ignored(mock_settings, mock_confluence_client):
    old_date = (datetime.now(timezone.utc) - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    mock_confluence_client.client.get_all_pages_from_space.return_value = {
        "results": [
            {
                "id": "123",
                "title": "Old Normal Page",
                "version": {"when": old_date, "number": 1},
            }
        ]
    }

    # Missing 'draft' or 'wip' label
    mock_confluence_client.client.get_page_labels.return_value = {
        "results": [{"name": "normal_label"}]
    }

    res = await confluence_stale_documentation_archiver_task()

    assert "Archived 0 pages" in res
    mock_confluence_client.client.get_page_labels.assert_called_once_with("123")
    mock_confluence_client.client.set_page_label.assert_not_called()
    mock_confluence_client.client.update_page.assert_not_called()

@pytest.mark.asyncio
async def test_already_archived_ignored(mock_settings, mock_confluence_client):
    old_date = (datetime.now(timezone.utc) - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    mock_confluence_client.client.get_all_pages_from_space.return_value = {
        "results": [
            {
                "id": "123",
                "title": "[ARCHIVED] Old Draft Page",
                "version": {"when": old_date, "number": 1},
            }
        ]
    }

    res = await confluence_stale_documentation_archiver_task()

    assert "Archived 0 pages" in res
    mock_confluence_client.client.get_page_labels.assert_not_called()
