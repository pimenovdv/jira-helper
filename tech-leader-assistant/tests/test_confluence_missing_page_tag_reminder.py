import pytest
from unittest.mock import MagicMock
from app.tasks import confluence_missing_page_tag_reminder_task
from app import tasks

@pytest.fixture
def mock_settings(mocker):
    mock = mocker.patch.object(tasks, "settings")
    def mock_get(key, default=""):
        if key == "OPENAI_API_KEY": return "sk-test"
        if key == "CONFLUENCE_TRACKED_SPACES": return "SPACE1"
        if key == "CONFLUENCE_REQUIRED_TAGS": return "tag1, tag2"
        return default
    mock.get.side_effect = mock_get
    return mock

@pytest.fixture
def mock_confluence_client(mocker):
    mock_cls = mocker.patch.object(tasks, "ConfluenceClient")
    mock_instance = mock_cls.return_value
    mock_instance.client = MagicMock()
    return mock_instance

@pytest.fixture
def mock_llm(mocker):
    mock_cls = mocker.patch.object(tasks, "ChatOpenAI")
    mock_instance = mock_cls.return_value
    mock_instance.ainvoke = mocker.AsyncMock(return_value=MagicMock(content="Mock reminder"))
    return mock_instance

@pytest.mark.asyncio
async def test_no_api_key(mocker):
    mock = mocker.patch.object(tasks, "settings")
    mock.get.return_value = ""
    res = await confluence_missing_page_tag_reminder_task()
    assert "skipped" in res
    assert "no OpenAI API key" in res

@pytest.mark.asyncio
async def test_no_required_tags(mock_settings, mocker):
    def mock_get(key, default=""):
        if key == "OPENAI_API_KEY": return "sk-test"
        if key == "CONFLUENCE_TRACKED_SPACES": return "SPACE1"
        if key == "CONFLUENCE_REQUIRED_TAGS": return ""
        return default
    mock_settings.get.side_effect = mock_get

    res = await confluence_missing_page_tag_reminder_task()
    assert "skipped" in res
    assert "no required tags" in res

@pytest.mark.asyncio
async def test_tags_present(mock_settings, mock_confluence_client, mock_llm):
    # Setup to return pages
    mock_confluence_client.client.get_all_pages_from_space.return_value = {
        "results": [{"id": "123", "title": "Test Page"}]
    }
    # Setup to return labels
    mock_confluence_client.client.get_page_labels.return_value = {
        "results": [{"name": "tag1"}, {"name": "tag2"}]
    }

    res = await confluence_missing_page_tag_reminder_task()

    mock_confluence_client.client.get_all_pages_from_space.assert_called_once()
    mock_confluence_client.client.get_page_labels.assert_called_once_with("123")
    mock_llm.ainvoke.assert_not_called()
    mock_confluence_client.client.add_comment.assert_not_called()
    assert "completed" in res

@pytest.mark.asyncio
async def test_tags_missing(mock_settings, mock_confluence_client, mock_llm):
    mock_confluence_client.client.get_all_pages_from_space.return_value = {
        "results": [{"id": "123", "title": "Test Page"}]
    }
    mock_confluence_client.client.get_page_labels.return_value = {
        "results": [{"name": "tag1"}]
    }
    mock_confluence_client.client.get_page_comments.return_value = {"results": []}

    res = await confluence_missing_page_tag_reminder_task()

    mock_llm.ainvoke.assert_called_once()
    mock_confluence_client.client.add_comment.assert_called_once()

    call_args = mock_confluence_client.client.add_comment.call_args[0]
    assert call_args[0] == "123"
    assert "Mock reminder" in call_args[1]
    assert "<!-- AUTO_GENERATED_CONFLUENCE_TAG_REMINDER -->" in call_args[1]
    assert "completed" in res

@pytest.mark.asyncio
async def test_tags_missing_but_already_reminded(mock_settings, mock_confluence_client, mock_llm):
    mock_confluence_client.client.get_all_pages_from_space.return_value = {
        "results": [{"id": "123", "title": "Test Page"}]
    }
    mock_confluence_client.client.get_page_labels.return_value = {
        "results": [{"name": "tag1"}]
    }
    mock_confluence_client.client.get_page_comments.return_value = {
        "results": [
            {
                "body": {
                    "storage": {
                        "value": "Here is a comment <!-- AUTO_GENERATED_CONFLUENCE_TAG_REMINDER -->"
                    }
                }
            }
        ]
    }

    res = await confluence_missing_page_tag_reminder_task()

    mock_llm.ainvoke.assert_not_called()
    mock_confluence_client.client.add_comment.assert_not_called()
    assert "completed" in res
