import pytest
import datetime
from datetime import timezone, timedelta
from unittest.mock import MagicMock
from app.tasks import confluence_author_summary_task
from app.clients import settings

@pytest.fixture(autouse=True)
def mock_chat_openai(mocker):
    return mocker.patch("langchain_openai.ChatOpenAI")

@pytest.fixture(autouse=True)
def mock_confluence_client(mocker):
    return mocker.patch("app.clients.confluence_client.ConfluenceClient")

@pytest.mark.asyncio
async def test_confluence_author_summary_missing_api_key(mock_confluence_client):
    original_key = settings.get("OPENAI_API_KEY")
    settings.set("OPENAI_API_KEY", "")

    result = await confluence_author_summary_task()

    settings.set("OPENAI_API_KEY", original_key)
    assert "skipped (no OpenAI API key)" in result

@pytest.mark.asyncio
async def test_confluence_author_summary_missing_spaces(mock_confluence_client):
    original_key = settings.get("OPENAI_API_KEY")
    original_spaces = settings.get("CONFLUENCE_TRACKED_SPACES")
    settings.set("OPENAI_API_KEY", "fake-key")
    settings.set("CONFLUENCE_TRACKED_SPACES", "")

    result = await confluence_author_summary_task()

    settings.set("OPENAI_API_KEY", original_key)
    settings.set("CONFLUENCE_TRACKED_SPACES", original_spaces)
    assert "skipped (no spaces configured)" in result

@pytest.mark.asyncio
async def test_confluence_author_summary_success(mock_confluence_client, mock_chat_openai, mocker):
    original_key = settings.get("OPENAI_API_KEY")
    original_spaces = settings.get("CONFLUENCE_TRACKED_SPACES")
    settings.set("OPENAI_API_KEY", "fake-key")
    settings.set("CONFLUENCE_TRACKED_SPACES", "DEV")

    mock_llm_instance = mock_chat_openai.return_value
    mock_response = mocker.MagicMock()
    mock_response.content = "<p>Test Summary</p>"
    mock_llm_instance.ainvoke = mocker.AsyncMock(return_value=mock_response)

    mock_client_instance = mock_confluence_client.return_value
    mock_client_instance.client = MagicMock()
    mock_client_instance.client.url = "http://confluence"

    now = datetime.datetime.now(timezone.utc)
    mock_client_instance.client.get_all_pages_from_space.return_value = {
        "results": [
            {
                "id": "1",
                "title": "Page 1",
                "version": {
                    "when": now.strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
                    "by": {
                        "displayName": "User One"
                    }
                }
            },
            {
                "id": "2",
                "title": "Page 2",
                "version": {
                    "when": now.strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
                    "by": {
                        "displayName": "User Two"
                    }
                }
            }
        ]
    }

    result = await confluence_author_summary_task()

    settings.set("OPENAI_API_KEY", original_key)
    settings.set("CONFLUENCE_TRACKED_SPACES", original_spaces)

    assert result == "Confluence author summary task completed"
    mock_llm_instance.ainvoke.assert_called_once()
    mock_client_instance.client.create_page.assert_called_once()
    call_kwargs = mock_client_instance.client.create_page.call_args.kwargs
    assert call_kwargs["space"] == "DEV"
    assert "Сводка активности авторов" in call_kwargs["title"]
    assert call_kwargs["body"] == "<p>Test Summary</p>"

@pytest.mark.asyncio
async def test_confluence_author_summary_no_recent_pages(mock_confluence_client, mock_chat_openai, mocker):
    original_key = settings.get("OPENAI_API_KEY")
    original_spaces = settings.get("CONFLUENCE_TRACKED_SPACES")
    settings.set("OPENAI_API_KEY", "fake-key")
    settings.set("CONFLUENCE_TRACKED_SPACES", "DEV")

    mock_llm_instance = mock_chat_openai.return_value

    mock_client_instance = mock_confluence_client.return_value
    mock_client_instance.client = MagicMock()

    now = datetime.datetime.now(timezone.utc)
    old_date = now - timedelta(days=10)
    mock_client_instance.client.get_all_pages_from_space.return_value = {
        "results": [
            {
                "id": "1",
                "title": "Page 1",
                "version": {
                    "when": old_date.strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
                    "by": {
                        "displayName": "User One"
                    }
                }
            }
        ]
    }

    result = await confluence_author_summary_task()

    settings.set("OPENAI_API_KEY", original_key)
    settings.set("CONFLUENCE_TRACKED_SPACES", original_spaces)

    assert "no recent contributions" in result
    mock_llm_instance.ainvoke.assert_not_called()
    mock_client_instance.client.create_page.assert_not_called()

@pytest.mark.asyncio
async def test_confluence_author_summary_exception_fetching(mock_confluence_client):
    original_key = settings.get("OPENAI_API_KEY")
    original_spaces = settings.get("CONFLUENCE_TRACKED_SPACES")
    settings.set("OPENAI_API_KEY", "fake-key")
    settings.set("CONFLUENCE_TRACKED_SPACES", "DEV")

    mock_client_instance = mock_confluence_client.return_value
    mock_client_instance.client = MagicMock()
    mock_client_instance.client.get_all_pages_from_space.side_effect = Exception("API down")

    result = await confluence_author_summary_task()

    settings.set("OPENAI_API_KEY", original_key)
    settings.set("CONFLUENCE_TRACKED_SPACES", original_spaces)

    assert "failed" in result
