import pytest
from unittest.mock import MagicMock, patch
from app.rag import retrieve, generate, RAGState

@pytest.fixture
def mock_settings(mocker):
    mocker.patch("app.rag.settings.get", side_effect=lambda k, default=None: "dummy" if default is None else default)

@patch("app.rag.OpenSearchVectorSearch")
@patch("app.rag.OpenAIEmbeddings")
def test_retrieve(mock_embeddings, mock_vectorsearch, mock_settings):
    # Setup mock
    mock_retriever = MagicMock()
    mock_doc = MagicMock()
    mock_doc.page_content = "Mocked document content"
    mock_retriever.invoke.return_value = [mock_doc]

    mock_vs_instance = MagicMock()
    mock_vs_instance.as_retriever.return_value = mock_retriever
    mock_vectorsearch.return_value = mock_vs_instance

    state: RAGState = {"question": "How to deploy?", "documents": [], "answer": ""}

    new_state = retrieve(state)

    assert "documents" in new_state
    assert len(new_state["documents"]) == 1
    assert new_state["documents"][0] == "Mocked document content"
    mock_retriever.invoke.assert_called_once_with("How to deploy?")

@patch("app.rag.ChatOpenAI")
def test_generate(mock_chatopenai, mock_settings):
    # LangChain prompt | llm behavior relies on standard interface
    # To mock the chain successfully, we'll patch the chain directly or ChatOpenAI properly.
    mock_llm_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Mocked answer"

    # Langchain uses Runnable protocol, `|` operator creates a RunnableSequence.
    # When `invoke` is called on the chain, it calls `invoke` on prompt then `invoke` on llm.
    mock_llm_instance.invoke.return_value = mock_response
    mock_chatopenai.return_value = mock_llm_instance

    state: RAGState = {"question": "How to deploy?", "documents": ["Doc 1 content"], "answer": ""}

    with patch("app.rag.ChatPromptTemplate") as mock_prompt_template:
        mock_prompt = MagicMock()
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response
        mock_prompt.__or__.return_value = mock_chain
        mock_prompt_template.from_template.return_value = mock_prompt

        new_state = generate(state)

    assert "answer" in new_state
    assert new_state["answer"] == "Mocked answer"
