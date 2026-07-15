import pytest
from app.deep_research import (
    planner_node, worker_node, reviewer_node, synthesizer_node, reviewer_router,
    DeepResearchState, SubTask, Plan, ReviewDecision
)
from langchain_core.messages import AIMessage, SystemMessage

@pytest.fixture
def mock_llms(mocker):
    mock_chat = mocker.patch("app.deep_research.ChatOpenAI")

    # Mocking for planner and reviewer (with_structured_output)
    instance = mock_chat.return_value
    structured_instance = mocker.MagicMock()
    instance.with_structured_output.return_value = structured_instance

    # Mocking for worker (create_react_agent)
    mock_create_react = mocker.patch("app.deep_research.create_react_agent")
    react_instance = mock_create_react.return_value

    return {
        "chat_class": mock_chat,
        "chat_instance": instance,
        "structured_instance": structured_instance,
        "create_react": mock_create_react,
        "react_instance": react_instance
    }

def test_planner_node(mock_llms):
    mock_llms["structured_instance"].invoke.return_value = Plan(
        steps=[
            SubTask(id="task_1", description="Step 1"),
            SubTask(id="task_2", description="Step 2")
        ]
    )

    state = {
        "original_query": "Test",
        "plan": [],
        "current_task_id": None,
        "completed_tasks": {},
        "task_results": {},
        "final_report": "",
        "messages": []
    }

    result = planner_node(state)
    assert len(result["plan"]) == 2
    assert result["plan"][0].id == "task_1"
    assert result["current_task_id"] == "task_1"

def test_worker_node(mock_llms):
    mock_llms["react_instance"].invoke.return_value = {
        "messages": [AIMessage(content="Worker result data")]
    }

    state = {
        "original_query": "Test",
        "plan": [SubTask(id="task_1", description="Step 1")],
        "current_task_id": "task_1",
        "completed_tasks": {},
        "task_results": {},
        "final_report": "",
        "messages": []
    }

    result = worker_node(state)
    assert result["task_results"]["task_1"] == "Worker result data"

def test_worker_node_no_task(mock_llms):
    state = {
        "original_query": "Test",
        "plan": [],
        "current_task_id": None,
        "completed_tasks": {},
        "task_results": {},
        "final_report": "",
        "messages": []
    }

    result = worker_node(state)
    assert result == {}

def test_reviewer_node_approved(mock_llms):
    mock_llms["structured_instance"].invoke.return_value = ReviewDecision(
        approved=True, feedback="Good"
    )

    state = {
        "original_query": "Test",
        "plan": [
            SubTask(id="task_1", description="Step 1"),
            SubTask(id="task_2", description="Step 2")
        ],
        "current_task_id": "task_1",
        "completed_tasks": {},
        "task_results": {"task_1": "Result"},
        "final_report": "",
        "messages": []
    }

    result = reviewer_node(state)
    assert result["completed_tasks"]["task_1"] == "approved"
    assert result["current_task_id"] == "task_2"

def test_reviewer_node_rejected(mock_llms):
    mock_llms["structured_instance"].invoke.return_value = ReviewDecision(
        approved=False, feedback="Bad data"
    )

    state = {
        "original_query": "Test",
        "plan": [
            SubTask(id="task_1", description="Step 1")
        ],
        "current_task_id": "task_1",
        "completed_tasks": {},
        "task_results": {"task_1": "Result"},
        "final_report": "",
        "messages": []
    }

    result = reviewer_node(state)
    assert "messages" in result
    assert result["messages"][0].content == "Рецензент отклонил результат. Причина: Bad data. Попробуй еще раз, используя эту обратную связь."

def test_synthesizer_node(mock_llms):
    mock_llms["chat_instance"].invoke.return_value = AIMessage(content="Final Synthesized Report")

    state = {
        "original_query": "Test",
        "plan": [],
        "current_task_id": None,
        "completed_tasks": {},
        "task_results": {"task_1": "Result 1", "task_2": "Result 2"},
        "final_report": "",
        "messages": []
    }

    result = synthesizer_node(state)
    assert result["final_report"] == "Final Synthesized Report"

def test_reviewer_router():
    # End of tasks
    state = {
        "current_task_id": None,
        "completed_tasks": {"task_1": "approved"}
    }
    assert reviewer_router(state) == "synthesizer"

    # Task was reviewed and approved (current_task_id changed to next, OR it's not rejected logic)
    # Actually, the logic in reviewer_router says if current_task_id is NOT in completed, it means rejected.
    # So if it IS in completed, it means we go to worker for the new task.
    # Wait, the state in router is the state AFTER the node updates it.

    # If approved, current_task_id becomes next task id. It's not in completed_tasks yet!
    # Let's say task_1 was approved. completed_tasks has {"task_1": "approved"}.
    # current_task_id is now "task_2". "task_2" is not in completed_tasks.
    # My logic: if current_task_id not in completed -> return "worker"
    # This works for approved (task_2 not in completed -> "worker").

    # What if rejected? current_task_id remains "task_1".
    # completed_tasks is empty.
    # current_task_id ("task_1") not in completed -> return "worker".

    # Wait, in both cases it returns "worker"! Let's verify:
    assert reviewer_router({"current_task_id": "task_2", "completed_tasks": {"task_1": "approved"}}) == "worker"
    assert reviewer_router({"current_task_id": "task_1", "completed_tasks": {}}) == "worker"
