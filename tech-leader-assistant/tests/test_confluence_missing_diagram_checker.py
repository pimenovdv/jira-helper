import pytest
from unittest.mock import AsyncMock, MagicMock
from app.tasks import confluence_missing_diagram_checker_task

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

@pytest.fixture(autouse=True)
def mock_settings(mocker):
    # completely replace the settings object so no real values are read
    mock = mocker.patch("app.tasks.settings")

    def side_effect(key, default=""):
        mapping = {
            "OPENAI_API_KEY": "test-key",
            "CONFLUENCE_TRACKED_SPACES": "SPACE1"
        }
        return mapping.get(key, default)

    mock.get.side_effect = side_effect

    # Also patch it in clients where ConfluenceClient gets initialized
    mocker.patch("app.clients.settings", mock)
    mocker.patch("app.clients.confluence_client.settings", mock)

    return mock

@pytest.fixture(autouse=True)
def mock_confluence_client(mocker):
    # Don't mock the ConfluenceClient *class*, mock what it *returns* when imported into tasks!
    mock_instance = MagicMock()
    mock_client = MagicMock()
    mock_instance.client = mock_client

    mocker.patch("app.tasks.ConfluenceClient", return_value=mock_instance)
    # also patch the actual class to prevent side effects just in case
    mocker.patch("app.clients.confluence_client.ConfluenceClient", return_value=mock_instance)
    return mock_client

@pytest.fixture
def mock_llm(mocker):
    mock = mocker.patch("langchain_openai.ChatOpenAI")
    mock_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Тестовое напоминание о диаграммах."
    mock_instance.ainvoke = AsyncMock(return_value=mock_response)
    mock.return_value = mock_instance
    return mock_instance

@pytest.mark.asyncio
async def test_confluence_missing_diagram_checker_task_has_diagram(
    mock_settings, mock_confluence_client, mock_llm
):
    mock_confluence_client.get_all_pages_from_space.return_value = {
        "results": [
            {
                "id": "1",
                "title": "Architecture Page 1",
                "body": {"storage": {"value": "<p>Some text</p><ac:image><ri:attachment ri:filename='arch.png'/></ac:image>"}},
                "history": {"lastUpdated": {"by": {"accountId": "user123"}}}
            }
        ]
    }

    mock_confluence_client.get_page_labels.return_value = {
        "results": [{"name": "architecture"}]
    }

    result = await confluence_missing_diagram_checker_task()
    assert "completed" in result

    mock_confluence_client.get_page_comments.assert_not_called()
    mock_confluence_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_confluence_missing_diagram_checker_task_no_diagram_no_comment(
    mock_settings, mock_confluence_client, mock_llm
):
    mock_confluence_client.get_all_pages_from_space.return_value = {
        "results": [
            {
                "id": "2",
                "title": "Architecture Page 2",
                "body": {"storage": {"value": "<p>Just text, no diagram</p>"}},
                "history": {"lastUpdated": {"by": {"accountId": "user123"}}}
            }
        ]
    }

    mock_confluence_client.get_page_labels.return_value = {
        "results": [{"name": "arch"}]
    }

    mock_confluence_client.get_page_comments.return_value = {
        "results": []
    }

    result = await confluence_missing_diagram_checker_task()
    assert "completed" in result

    mock_confluence_client.add_comment.assert_called_once()
    args, _ = mock_confluence_client.add_comment.call_args
    assert args[0] == "2"
    assert "<!-- AUTO_GENERATED_CONFLUENCE_MISSING_DIAGRAM_REMINDER -->" in args[1]
    assert "[~accountid:user123]" in args[1]
    assert "Тестовое напоминание о диаграммах." in args[1]

@pytest.mark.asyncio
async def test_confluence_missing_diagram_checker_task_already_reminded(
    mock_settings, mock_confluence_client, mock_llm
):
    mock_confluence_client.get_all_pages_from_space.return_value = {
        "results": [
            {
                "id": "3",
                "title": "Architecture Page 3",
                "body": {"storage": {"value": "<p>No diagram here either</p>"}},
                "history": {"lastUpdated": {"by": {"accountId": "user123"}}}
            }
        ]
    }

    mock_confluence_client.get_page_labels.return_value = {
        "results": [{"name": "architecture"}]
    }

    mock_confluence_client.get_page_comments.return_value = {
        "results": [
            {
                "body": {
                    "storage": {
                        "value": "<!-- AUTO_GENERATED_CONFLUENCE_MISSING_DIAGRAM_REMINDER -->\nOld reminder"
                    }
                }
            }
        ]
    }

    result = await confluence_missing_diagram_checker_task()
    assert "completed" in result

    mock_confluence_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_confluence_missing_diagram_checker_task_missing_config(
    mock_settings, mock_confluence_client, mock_llm
):
    def missing_config_side_effect(key, default=""):
        mapping = {
            "OPENAI_API_KEY": "test-key",
            "CONFLUENCE_TRACKED_SPACES": ""
        }
        return mapping.get(key, default)

    mock_settings.get.side_effect = missing_config_side_effect

    result = await confluence_missing_diagram_checker_task()
    assert "skipped" in result
    mock_confluence_client.get_all_pages_from_space.assert_not_called()

@pytest.mark.asyncio
async def test_confluence_missing_diagram_checker_task_missing_openai_key(
    mock_settings, mock_confluence_client, mock_llm
):
    def missing_openai_key_side_effect(key, default=""):
        mapping = {
            "OPENAI_API_KEY": "",
            "CONFLUENCE_TRACKED_SPACES": "SPACE1"
        }
        return mapping.get(key, default)

    mock_settings.get.side_effect = missing_openai_key_side_effect

    result = await confluence_missing_diagram_checker_task()
    assert "skipped" in result
    mock_confluence_client.get_all_pages_from_space.assert_not_called()
