import pytest

@pytest.fixture
def mock_driver(mocker):
    mock_neo4j = mocker.patch('app.clients.neo4j_client.GraphDatabase.driver')
    return mock_neo4j.return_value

def test_link_task_to_project_exception(mocker, mock_driver):
    mocker.patch('app.clients.settings.get', side_effect=lambda k: "dummy")
    from app.clients.neo4j_client import Neo4jClient
    client = Neo4jClient()

    mock_session = mocker.MagicMock()
    mock_session.run.side_effect = Exception("error")
    mock_driver.session.return_value.__enter__.return_value = mock_session

    client.link_task_to_project("T-1", "P-1")

def test_link_release_to_project_exception(mocker, mock_driver):
    mocker.patch('app.clients.settings.get', side_effect=lambda k: "dummy")
    from app.clients.neo4j_client import Neo4jClient
    client = Neo4jClient()

    mock_session = mocker.MagicMock()
    mock_session.run.side_effect = Exception("error")
    mock_driver.session.return_value.__enter__.return_value = mock_session

    client.link_release_to_project("R-1", "P-1")

def test_cleanup_ghost_nodes_exception(mocker, mock_driver):
    mocker.patch('app.clients.settings.get', side_effect=lambda k: "dummy")
    from app.clients.neo4j_client import Neo4jClient
    client = Neo4jClient()

    mock_session = mocker.MagicMock()
    mock_session.run.side_effect = Exception("error")
    mock_driver.session.return_value.__enter__.return_value = mock_session

    client.cleanup_ghost_nodes(["T-1"], ["R-1"], ["P-1"])
