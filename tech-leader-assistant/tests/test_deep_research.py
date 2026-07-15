import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.deep_research import Plan, SubTask, ReviewDecision

client = TestClient(app)

@pytest.fixture
def mock_deep_research_graph(mocker):
    mock_graph = mocker.patch("app.main.deep_research_graph")
    return mock_graph

def test_deep_research_endpoint_success(mock_deep_research_graph):
    # Mock the return of the graph invocation
    mock_result = {
        "final_report": "Отчет по исследованию готов.",
        "plan": [
            SubTask(id="task_1", description="Шаг 1", dependencies=[])
        ],
        "task_results": {
            "task_1": "Результат шага 1"
        }
    }
    mock_deep_research_graph.invoke.return_value = mock_result

    response = client.post("/api/deep-research", json={"query": "Тестовый запрос"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["report"] == "Отчет по исследованию готов."
    assert len(data["plan"]) == 1
    assert data["plan"][0]["id"] == "task_1"
    assert data["task_results"]["task_1"] == "Результат шага 1"

    mock_deep_research_graph.invoke.assert_called_once()
    called_state = mock_deep_research_graph.invoke.call_args[0][0]
    assert called_state["original_query"] == "Тестовый запрос"

def test_deep_research_endpoint_exception(mock_deep_research_graph):
    mock_deep_research_graph.invoke.side_effect = Exception("Graph error")

    response = client.post("/api/deep-research", json={"query": "Тестовый запрос"})
    assert response.status_code == 500
    assert "Graph error" in response.json()["detail"]
