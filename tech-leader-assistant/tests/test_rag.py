import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Import the new structures
from app.rag import agent

@pytest.fixture
def mock_settings(mocker):
    # Need to mock settings dynamically if it's imported as a module attribute in rag.py
    # or just use patch on `app.rag.settings`
    mocker.patch("app.rag.settings.get", side_effect=lambda k, default=None: "dummy" if default is None else default)

@patch("app.rag.ChatOpenAI")
def test_agent_node(mock_chatopenai, mock_settings):
    # Setup the mock ChatOpenAI instance and its bound version
    mock_llm_instance = MagicMock()
    mock_bound_llm = MagicMock()

    mock_llm_instance.bind_tools.return_value = mock_bound_llm
    mock_chatopenai.return_value = mock_llm_instance

    # Mock response from LLM
    mock_response_message = AIMessage(content="I can help with that.")
    mock_bound_llm.invoke.return_value = mock_response_message

    state = {"messages": [HumanMessage(content="What is the status of TLA-123?")]}

    new_state = agent(state)

    assert "messages" in new_state
    assert len(new_state["messages"]) == 1
    assert new_state["messages"][0] == mock_response_message

    # Verify invoke was called correctly with system message and user message
    call_args = mock_bound_llm.invoke.call_args[0][0]
    assert len(call_args) == 2
    assert isinstance(call_args[0], SystemMessage)
    assert call_args[1].content == "What is the status of TLA-123?"
