import pytest
from unittest.mock import MagicMock
from app.tasks import confluence_missing_owner_warning_task
import app.tasks as tasks

@pytest.fixture
def mock_dependencies(mocker):
    # Mock settings imported directly from app.clients in app.tasks
    mock_settings = mocker.patch.object(tasks, "settings")
    def mock_get(key, default=""):
        if key == "OPENAI_API_KEY": return "sk-test"
        if key == "CONFLUENCE_TRACKED_SPACES": return "SPACE1"
        return default
    mock_settings.get.side_effect = mock_get

    # Also mock app.clients.settings directly
    mock_clients_settings = mocker.patch("app.clients.settings")
    mock_clients_settings.get.side_effect = mock_get

    # Patch the real ConfluenceClient class
    mock_cc_cls = mocker.patch("app.clients.confluence_client.ConfluenceClient")
    mock_cc = mock_cc_cls.return_value
    mock_cc.client = MagicMock()

    # And patch the reference to it in tasks just in case
    mocker.patch.object(tasks, "ConfluenceClient", return_value=mock_cc)

    # Note: the test failed with "Incorrect API key provided", which means the ChatOpenAI inside
    # langchain wasn't mocked properly, and actually tried to hit OpenAI.
    # We must patch langchain_openai.ChatOpenAI directly as it is where it actually resides
    mock_llm_cls = mocker.patch("langchain_openai.ChatOpenAI")
    mock_llm = mock_llm_cls.return_value
    mock_llm.ainvoke = mocker.AsyncMock(return_value=MagicMock(content="Please add an owner tag."))

    # And patch the reference in app.tasks just in case
    mocker.patch.object(tasks, "ChatOpenAI", return_value=mock_llm)

    return {
        "settings": mock_settings,
        "clients_settings": mock_clients_settings,
        "confluence_client": mock_cc,
        "llm": mock_llm,
    }

@pytest.mark.asyncio
async def test_no_api_key(mock_dependencies):
    def side_effect(key, default=""):
        if key == "OPENAI_API_KEY": return ""
        if key == "CONFLUENCE_TRACKED_SPACES": return "SPACE1"
        return default
    mock_dependencies["settings"].get.side_effect = side_effect
    mock_dependencies["clients_settings"].get.side_effect = side_effect

    res = await confluence_missing_owner_warning_task()
    assert "skipped" in res
    assert "no OpenAI API key" in res

@pytest.mark.asyncio
async def test_no_spaces(mock_dependencies):
    def side_effect(key, default=""):
        if key == "OPENAI_API_KEY": return "sk-test"
        if key == "CONFLUENCE_TRACKED_SPACES": return ""
        return default
    mock_dependencies["settings"].get.side_effect = side_effect
    mock_dependencies["clients_settings"].get.side_effect = side_effect

    res = await confluence_missing_owner_warning_task()
    assert "skipped" in res
    assert "no spaces configured" in res

@pytest.mark.asyncio
async def test_success(mock_dependencies):
    mock_cc = mock_dependencies["confluence_client"]

    # Setup to return pages
    def get_all_pages_side_effect(space, **kwargs):
        if space == "SPACE1":
            return {
                "results": [
                    {
                        "id": "1",
                        "title": "Page 1",
                        "history": {"lastUpdated": {"by": {"accountId": "user1"}}}
                    },
                    {
                        "id": "2",
                        "title": "Page 2",
                        "history": {"lastUpdated": {"by": {"accountId": "user2"}}}
                    }
                ]
            }
        return {"results": []}
    mock_cc.client.get_all_pages_from_space.side_effect = get_all_pages_side_effect

    # Setup to return labels
    def get_page_labels_side_effect(page_id):
        if page_id == "1":
            return {"results": [{"name": "owner:user1"}, {"name": "test"}]}
        else:
            return {"results": [{"name": "test"}]}
    mock_cc.client.get_page_labels.side_effect = get_page_labels_side_effect

    # Setup to return comments
    def get_page_comments_side_effect(page_id, **kwargs):
        return {"results": []}
    mock_cc.client.get_page_comments.side_effect = get_page_comments_side_effect

    res = await confluence_missing_owner_warning_task()

    assert "completed" in res
    mock_cc.client.add_comment.assert_called_once()

    args, kwargs = mock_cc.client.add_comment.call_args
    assert args[0] == "2"
    assert "<!-- AUTO_GENERATED_CONFLUENCE_MISSING_OWNER_REMINDER -->" in args[1]
    assert "[~accountid:user2]" in args[1]
    assert "Please add an owner tag." in args[1]

@pytest.mark.asyncio
async def test_already_reminded(mock_dependencies):
    mock_cc = mock_dependencies["confluence_client"]

    mock_cc.client.get_all_pages_from_space.return_value = {
        "results": [
            {
                "id": "3",
                "title": "Page 3",
                "history": {"lastUpdated": {"by": {"accountId": "user3"}}}
            }
        ]
    }

    mock_cc.client.get_page_labels.return_value = {"results": [{"name": "test"}]}

    mock_cc.client.get_page_comments.return_value = {
        "results": [
            {
                "body": {
                    "storage": {
                        "value": "<!-- AUTO_GENERATED_CONFLUENCE_MISSING_OWNER_REMINDER -->\nPlease add an owner tag."
                    }
                }
            }
        ]
    }

    res = await confluence_missing_owner_warning_task()

    assert "completed" in res
    mock_cc.client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_exception_handling(mock_dependencies):
    mock_cc = mock_dependencies["confluence_client"]
    mock_cc.client.get_all_pages_from_space.side_effect = Exception("API error")

    res = await confluence_missing_owner_warning_task()

    assert "completed" in res

import pytest
from app.tasks import confluence_missing_owner_warning_task

@pytest.mark.asyncio
async def test_confluence_missing_owner_warning_coverage_no_spaces(mocker):
    mock_settings = mocker.patch("app.tasks.settings")
    mock_settings.get.side_effect = lambda key, default="": {"OPENAI_API_KEY": "sk-test", "CONFLUENCE_TRACKED_SPACES": "   "}.get(key, default)
    mock_clients_settings = mocker.patch("app.clients.settings")
    mock_clients_settings.get.side_effect = lambda key, default="": {"OPENAI_API_KEY": "sk-test", "CONFLUENCE_TRACKED_SPACES": "   "}.get(key, default)

    res = await confluence_missing_owner_warning_task()
    assert "skipped" in res
    assert "no spaces configured" in res
