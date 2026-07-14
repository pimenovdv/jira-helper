import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from app.main import app
from app.clients import settings

client = TestClient(app)

@pytest.fixture
def mock_code_review_env(mocker):
    # Mock GitLabClient
    mock_gitlab_cls = mocker.patch("app.main.GitLabClient")
    mock_gitlab = mock_gitlab_cls.return_value
    mock_gitlab.get_merge_request_changes.return_value = {
        "changes": [
            {
                "new_path": "test.py",
                "diff": "@@ -1 +1,2 @@\n-old\n+new"
            }
        ]
    }
    mock_gitlab.create_merge_request_note.return_value = True

    # Mock OpenSearchVectorSearch
    mock_os_cls = mocker.patch("app.main.OpenSearchVectorSearch")
    mock_retriever = MagicMock()
    mock_doc = MagicMock()
    mock_doc.page_content = "Всегда пишите тесты."
    mock_retriever.invoke.return_value = [mock_doc]
    mock_os_cls.return_value.as_retriever.return_value = mock_retriever

    # Mock ChatOpenAI
    mock_llm_cls = mocker.patch("app.main.ChatOpenAI")

    # Mock ChatPromptTemplate
    mock_prompt_cls = mocker.patch("app.main.ChatPromptTemplate")
    mock_prompt = mock_prompt_cls.from_template.return_value

    # Mock the chain invocation
    # prompt | llm produces a chain.
    # The simplest way is to mock __or__ on the prompt
    mock_chain = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Хороший код!"
    mock_chain.invoke.return_value = mock_response
    mock_prompt.__or__.return_value = mock_chain

    return {
        "gitlab": mock_gitlab,
        "os": mock_os_cls,
        "llm": mock_llm_cls,
        "prompt": mock_prompt_cls
    }

def test_automated_code_review_success(mock_code_review_env):
    settings.set("OPENAI_API_KEY", "test-key")

    response = client.post("/api/projects/123/merge_requests/456/review")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "review": "Хороший код!"}

    mock_code_review_env["gitlab"].get_merge_request_changes.assert_called_once_with("123", 456)
    mock_code_review_env["gitlab"].create_merge_request_note.assert_called_once_with("123", 456, "Хороший код!")

def test_automated_code_review_no_changes(mock_code_review_env):
    mock_code_review_env["gitlab"].get_merge_request_changes.return_value = {}

    response = client.post("/api/projects/123/merge_requests/456/review")
    assert response.status_code == 404
    assert "MR or changes not found" in response.json()["detail"]

def test_automated_code_review_no_api_key(mock_code_review_env):
    settings.set("OPENAI_API_KEY", "")

    response = client.post("/api/projects/123/merge_requests/456/review")
    assert response.status_code == 500
    assert "OPENAI_API_KEY not found" in response.json()["detail"]

def test_automated_code_review_gitlab_failure(mock_code_review_env):
    settings.set("OPENAI_API_KEY", "test-key")
    mock_code_review_env["gitlab"].create_merge_request_note.return_value = False

    response = client.post("/api/projects/123/merge_requests/456/review")
    assert response.status_code == 500
    assert "Failed to post note to GitLab" in response.json()["detail"]
