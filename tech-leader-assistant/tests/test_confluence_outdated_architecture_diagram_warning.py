import pytest
from unittest.mock import MagicMock
from app.tasks import confluence_outdated_architecture_diagram_warning_task
from datetime import datetime, timezone, timedelta

@pytest.mark.asyncio
async def test_confluence_outdated_architecture_diagram_warning_task(mocker):
    mock_settings = MagicMock()
    mock_settings.get.return_value = "DEV"
    mocker.patch("app.clients.settings", mock_settings)

    mock_confluence = MagicMock()
    mocker.patch("app.tasks.ConfluenceClient", return_value=mock_confluence)

    now = datetime.now(timezone.utc)
    old_date = (now - timedelta(days=400)).isoformat()
    recent_date = (now - timedelta(days=100)).isoformat()

    page_old = {
        "id": "1",
        "body": {"storage": {"value": "<p>Architecture doc</p>"}},
        "history": {"lastUpdated": {"when": old_date, "by": {"accountId": "user123"}}}
    }

    page_recent = {
        "id": "2",
        "body": {"storage": {"value": "<p>Architecture doc</p>"}},
        "history": {"lastUpdated": {"when": recent_date, "by": {"accountId": "user456"}}}
    }

    mock_confluence.cql.return_value = {"results": [page_old, page_recent]}
    mock_confluence.get_page_comments.return_value = {"results": []}

    await confluence_outdated_architecture_diagram_warning_task()

    mock_confluence.add_comment.assert_called_once_with(
        "1",
        "<!-- AUTO_GENERATED_OUTDATED_ARCHITECTURE_DIAGRAM_WARNING -->\nHi [~accountid:user123],\n\nIt looks like this page contains an architecture diagram that hasn't been updated in over a year. To ensure our technical documentation remains accurate, please review the diagram and update it if necessary."
    )

@pytest.mark.asyncio
async def test_confluence_outdated_architecture_diagram_already_warned(mocker):
    mock_settings = MagicMock()
    mock_settings.get.return_value = "DEV"
    mocker.patch("app.clients.settings", mock_settings)

    mock_confluence = MagicMock()
    mocker.patch("app.tasks.ConfluenceClient", return_value=mock_confluence)

    now = datetime.now(timezone.utc)
    old_date = (now - timedelta(days=400)).isoformat()

    page_old = {
        "id": "1",
        "body": {"storage": {"value": "<p>Architecture doc</p>"}},
        "history": {"lastUpdated": {"when": old_date, "by": {"accountId": "user123"}}}
    }

    mock_confluence.cql.return_value = {"results": [page_old]}

    mock_confluence.get_page_comments.return_value = {
        "results": [{"body": {"storage": {"value": "<!-- AUTO_GENERATED_OUTDATED_ARCHITECTURE_DIAGRAM_WARNING -->"}}}]
    }

    await confluence_outdated_architecture_diagram_warning_task()

    mock_confluence.add_comment.assert_not_called()
