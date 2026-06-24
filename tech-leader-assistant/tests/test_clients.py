import pytest

def test_gitlab_ping(mocker):
    # Mock settings
    mocker.patch('app.clients.settings.get', side_effect=lambda k: "dummy")
    mock_gitlab = mocker.patch('app.clients.gitlab_client.gitlab.Gitlab')
    mock_instance = mock_gitlab.return_value
    mock_instance.auth.return_value = None

    from app.clients.gitlab_client import GitLabClient
    client = GitLabClient()
    result = client.ping()

    assert result["status"] == "ok"
    assert result["service"] == "GitLab"
    mock_instance.auth.assert_called_once()

def test_jira_ping(mocker):
    mocker.patch('app.clients.settings.get', side_effect=lambda k: "dummy")
    mock_jira = mocker.patch('app.clients.jira_client.JIRA')
    mock_instance = mock_jira.return_value
    mock_instance.myself.return_value = None

    from app.clients.jira_client import JiraClient
    client = JiraClient()
    result = client.ping()

    assert result["status"] == "ok"
    assert result["service"] == "Jira"
    mock_instance.myself.assert_called_once()

def test_confluence_ping(mocker):
    mocker.patch('app.clients.settings.get', side_effect=lambda k: "dummy")
    mock_conf = mocker.patch('app.clients.confluence_client.Confluence')
    mock_instance = mock_conf.return_value
    mock_instance.get_all_spaces.return_value = []

    from app.clients.confluence_client import ConfluenceClient
    client = ConfluenceClient()
    result = client.ping()

    assert result["status"] == "ok"
    assert result["service"] == "Confluence"
    mock_instance.get_all_spaces.assert_called_once_with(start=0, limit=1)

def test_neo4j_ping(mocker):
    mocker.patch('app.clients.settings.get', side_effect=lambda k: "dummy")
    mock_neo4j = mocker.patch('app.clients.neo4j_client.GraphDatabase.driver')
    mock_driver_instance = mock_neo4j.return_value
    mock_driver_instance.verify_connectivity.return_value = None

    from app.clients.neo4j_client import Neo4jClient
    client = Neo4jClient()
    result = client.ping()

    assert result["status"] == "ok"
    assert result["service"] == "Neo4j"
    mock_driver_instance.verify_connectivity.assert_called_once()

def test_opensearch_ping(mocker):
    mocker.patch('app.clients.settings.get', side_effect=lambda k: "dummy")
    mock_os = mocker.patch('app.clients.opensearch_client.OpenSearch')
    mock_instance = mock_os.return_value
    mock_instance.ping.return_value = True

    from app.clients.opensearch_client import OpenSearchClient
    client = OpenSearchClient()
    result = client.ping()

    assert result["status"] == "ok"
    assert result["service"] == "OpenSearch"
    mock_instance.ping.assert_called_once()
