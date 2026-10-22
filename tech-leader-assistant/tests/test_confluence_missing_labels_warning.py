import pytest
from unittest.mock import MagicMock, AsyncMock
from app.tasks import confluence_missing_labels_warning_task

@pytest.fixture
def mock_settings(mocker):
    mock_set = mocker.patch("app.tasks.settings")
    # Provide necessary settings
    def get_setting(key, default=""):
        if key == "OPENAI_API_KEY":
            return "test-key"
        if key == "CONFLUENCE_TRACKED_SPACES":
            return "TESTSPACE"
        return default
    mock_set.get.side_effect = get_setting
    return mock_set

@pytest.fixture
def mock_confluence_client(mocker):
    mock_client = MagicMock()
    # Mocking the client instance itself since it's instantiated inside the task
    mock_class = mocker.patch("app.tasks.ConfluenceClient")
    mock_class.return_value = mock_client
    return mock_client

@pytest.fixture
def mock_llm(mocker):
    mock_llm_instance = MagicMock()
    mock_llm_instance.ainvoke = AsyncMock(return_value=MagicMock(content="Please add labels."))
    mock_llm_class = mocker.patch("app.tasks.ChatOpenAI")
    mock_llm_class.return_value = mock_llm_instance
    return mock_llm_instance

@pytest.mark.asyncio
async def test_confluence_missing_labels_warning_no_labels(mock_settings, mock_confluence_client, mock_llm):
    # Setup pages
    page_id = "12345"
    mock_confluence_client.client.get_all_pages_from_space.return_value = {
        "results": [
            {
                "id": page_id,
                "history": {
                    "lastUpdated": {
                        "by": {
                            "accountId": "test-user-id"
                        }
                    }
                }
            }
        ]
    }

    # Setup labels (none)
    mock_confluence_client.client.get_page_labels.return_value = {"results": []}

    # Setup comments (no previous warning)
    mock_confluence_client.client.get_page_comments.return_value = {"results": []}

    await confluence_missing_labels_warning_task()

    # Verify that add_comment was called with the warning marker and mention
    mock_confluence_client.client.add_comment.assert_called_once()
    call_args = mock_confluence_client.client.add_comment.call_args[0]
    assert call_args[0] == page_id
    assert "Please add labels." in call_args[1]
    assert "<!-- AUTO_GENERATED_CONFLUENCE_MISSING_LABELS_WARNING -->" in call_args[1]
    # Verify that LLM was called with the correct prompt containing the author mention
    mock_llm.ainvoke.assert_called_once()
    llm_prompt = mock_llm.ainvoke.call_args[0][0][0].content
    assert "[~accountid:test-user-id]" in llm_prompt


@pytest.mark.asyncio
async def test_confluence_missing_labels_warning_has_labels(mock_settings, mock_confluence_client, mock_llm):
    page_id = "12345"
    mock_confluence_client.client.get_all_pages_from_space.return_value = {
        "results": [{"id": page_id}]
    }

    # Setup labels (has label)
    mock_confluence_client.client.get_page_labels.return_value = {"results": [{"name": "test-label"}]}

    await confluence_missing_labels_warning_task()

    # Verify no comment was added
    mock_confluence_client.client.add_comment.assert_not_called()
    mock_llm.ainvoke.assert_not_called()

@pytest.mark.asyncio
async def test_confluence_missing_labels_warning_already_warned(mock_settings, mock_confluence_client, mock_llm):
    page_id = "12345"
    mock_confluence_client.client.get_all_pages_from_space.return_value = {
        "results": [{"id": page_id}]
    }

    # Setup labels (none)
    mock_confluence_client.client.get_page_labels.return_value = {"results": []}

    # Setup comments (already warned)
    mock_confluence_client.client.get_page_comments.return_value = {
        "results": [
            {
                "body": {
                    "storage": {
                        "value": "Existing comment.\n\n<!-- AUTO_GENERATED_CONFLUENCE_MISSING_LABELS_WARNING -->"
                    }
                }
            }
        ]
    }

    await confluence_missing_labels_warning_task()

    # Verify no new comment was added
    mock_confluence_client.client.add_comment.assert_not_called()
    mock_llm.ainvoke.assert_not_called()

@pytest.mark.asyncio
async def test_confluence_missing_labels_warning_no_api_key(mock_settings, mock_confluence_client, mock_llm, mocker):
    mock_settings.get.side_effect = lambda key, default="": "" if key == "OPENAI_API_KEY" else default

    result = await confluence_missing_labels_warning_task()
    assert result == "Confluence missing labels warning task skipped (no OpenAI API key)"
    mock_confluence_client.client.get_all_pages_from_space.assert_not_called()
