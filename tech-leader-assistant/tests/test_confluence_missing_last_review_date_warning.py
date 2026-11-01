import pytest
from unittest.mock import MagicMock
from app.tasks import confluence_missing_last_review_date_warning_task

@pytest.mark.asyncio
async def test_confluence_missing_last_review_date_warning_task(mocker):
    mock_settings = MagicMock()
    mock_settings.get.return_value = "DEV"
    mocker.patch("app.clients.settings", mock_settings)

    mock_confluence = MagicMock()
    mocker.patch("app.tasks.ConfluenceClient", return_value=mock_confluence)

    page_missing = {
        "id": "1",
        "body": {"storage": {"value": "<p>Some doc</p>"}},
        "history": {"lastUpdated": {"by": {"accountId": "user123"}}}
    }

    mock_confluence.cql.return_value = {"results": [page_missing]}
    mock_confluence.get_page_comments.return_value = {"results": []}

    await confluence_missing_last_review_date_warning_task()

    mock_confluence.add_comment.assert_called_once_with(
        "1",
        "<!-- AUTO_GENERATED_MISSING_LAST_REVIEW_DATE_WARNING -->\nHi [~accountid:user123],\n\nIt looks like this page is missing a **Last Reviewed Date** section. Keeping documentation up to date is crucial. Please add a 'Last Reviewed Date' to the top or bottom of the page."
    )

@pytest.mark.asyncio
async def test_confluence_missing_last_review_date_already_warned(mocker):
    mock_settings = MagicMock()
    mock_settings.get.return_value = "DEV"
    mocker.patch("app.clients.settings", mock_settings)

    mock_confluence = MagicMock()
    mocker.patch("app.tasks.ConfluenceClient", return_value=mock_confluence)

    page_missing = {
        "id": "1",
        "body": {"storage": {"value": "<p>Some doc</p>"}},
    }

    mock_confluence.cql.return_value = {"results": [page_missing]}

    mock_confluence.get_page_comments.return_value = {
        "results": [{"body": {"storage": {"value": "<!-- AUTO_GENERATED_MISSING_LAST_REVIEW_DATE_WARNING -->"}}}]
    }

    await confluence_missing_last_review_date_warning_task()

    mock_confluence.add_comment.assert_not_called()
