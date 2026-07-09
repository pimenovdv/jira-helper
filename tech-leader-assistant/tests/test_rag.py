import pytest
from unittest.mock import MagicMock, patch
from app.rag import agent, finalize, should_continue, RAGState
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

@pytest.fixture
def mock_settings(mocker):
    mocker.patch("app.rag.settings.get", side_effect=lambda k, default=None: "dummy" if default is None else default)

@patch("app.rag.ChatOpenAI")
def test_agent_first_call(mock_chatopenai, mock_settings):
    mock_llm_instance = MagicMock()
    mock_response = AIMessage(content="Here is a plan", tool_calls=[{"name": "query_jira", "args": {"jql": "project=PROJ"}, "id": "123"}])
    mock_llm_instance.bind_tools.return_value.invoke.return_value = mock_response
    mock_chatopenai.return_value = mock_llm_instance

    state: RAGState = {"question": "What is status?", "messages": [], "answer": "", "documents": []}
    new_state = agent(state)

    assert "messages" in new_state
    assert len(new_state["messages"]) == 3
    assert new_state["messages"][2] == mock_response

def test_should_continue_tools():
    state = {"messages": [AIMessage(content="", tool_calls=[{"name": "test", "args": {}, "id": "123"}])]}
    assert should_continue(state) == "tools"

def test_should_continue_finalize():
    state = {"messages": [AIMessage(content="Final answer")]}
    assert should_continue(state) == "finalize"

def test_finalize():
    state = {
        "messages": [
            HumanMessage(content="Query"),
            AIMessage(content="", tool_calls=[{"name": "test", "args": {}, "id": "123"}]),
            ToolMessage(content="Tool result", tool_call_id="123", name="test"),
            AIMessage(content="Final answer")
        ]
    }

    new_state = finalize(state)
    assert new_state["answer"] == "Final answer"
    assert new_state["documents"] == ["Tool result"]
