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

def test_get_project_branches(mocker):
    mocker.patch('app.clients.settings.get', side_effect=lambda k: "dummy")
    mock_gitlab = mocker.patch('app.clients.gitlab_client.gitlab.Gitlab')
    mock_instance = mock_gitlab.return_value
    mock_project = mocker.MagicMock()
    mock_instance.projects.get.return_value = mock_project
    mock_project.branches.list.return_value = ["branch1", "branch2"]

    from app.clients.gitlab_client import GitLabClient
    client = GitLabClient()
    result = client.get_project_branches("1")

    assert result == ["branch1", "branch2"]
    mock_instance.projects.get.assert_called_once_with("1")
    mock_project.branches.list.assert_called_once_with(all=True)

def test_get_project_versions(mocker):
    mocker.patch('app.clients.settings.get', side_effect=lambda k: "dummy")
    mock_jira = mocker.patch('app.clients.jira_client.JIRA')
    mock_instance = mock_jira.return_value
    mock_instance.project_versions.return_value = ["v1", "v2"]

    from app.clients.jira_client import JiraClient
    client = JiraClient()
    result = client.get_project_versions("PROJ1")

    assert result == ["v1", "v2"]
    mock_instance.project_versions.assert_called_once_with("PROJ1")

def test_search_issues(mocker):
    mocker.patch('app.clients.settings.get', side_effect=lambda k: "dummy")
    mock_jira = mocker.patch('app.clients.jira_client.JIRA')
    mock_instance = mock_jira.return_value
    mock_instance.search_issues.return_value = ["issue1", "issue2"]

    from app.clients.jira_client import JiraClient
    client = JiraClient()
    result = client.search_issues("project = PROJ1")

    assert result == ["issue1", "issue2"]
    mock_instance.search_issues.assert_called_once_with("project = PROJ1", maxResults=100)


from app.clients.gitlab_client import GitLabClient

def test_gitlab_client_is_branch_merged_true(mocker):
    mocker.patch("app.clients.gitlab_client.settings.get", side_effect=lambda k, d="": "")
    client = GitLabClient()
    mock_project = mocker.MagicMock()
    # return empty commits
    mock_project.repository_compare.return_value = {"commits": []}

    mock_gitlab_instance = mocker.MagicMock()
    mock_gitlab_instance.projects.get.return_value = mock_project
    client.client = mock_gitlab_instance

    result = client.is_branch_merged("proj1", "feature/1", "release/1")
    assert result is True
    mock_project.repository_compare.assert_called_once_with(from_="release/1", to="feature/1")

def test_gitlab_client_is_branch_merged_false(mocker):
    mocker.patch("app.clients.gitlab_client.settings.get", side_effect=lambda k, d="": "")
    client = GitLabClient()
    mock_project = mocker.MagicMock()
    # return some commits
    mock_project.repository_compare.return_value = {"commits": [{"id": "abc"}]}

    mock_gitlab_instance = mocker.MagicMock()
    mock_gitlab_instance.projects.get.return_value = mock_project
    client.client = mock_gitlab_instance

    result = client.is_branch_merged("proj1", "feature/1", "release/1")
    assert result is False


def test_gitlab_client_delete_branch_success(mocker):
    mocker.patch("app.clients.gitlab_client.settings.get", side_effect=lambda k, d="": "")
    client = GitLabClient()
    mock_project = mocker.MagicMock()
    mock_gitlab_instance = mocker.MagicMock()
    mock_gitlab_instance.projects.get.return_value = mock_project
    client.client = mock_gitlab_instance

    result = client.delete_branch("proj1", "feature/old")
    assert result is True
    mock_gitlab_instance.projects.get.assert_called_once_with("proj1")
    mock_project.branches.delete.assert_called_once_with("feature/old")

def test_gitlab_client_delete_branch_exception(mocker):
    mocker.patch("app.clients.gitlab_client.settings.get", side_effect=lambda k, d="": "")
    client = GitLabClient()
    mock_gitlab_instance = mocker.MagicMock()
    mock_gitlab_instance.projects.get.side_effect = Exception("Error")
    client.client = mock_gitlab_instance

    result = client.delete_branch("proj1", "feature/old")
    assert result is False

def test_gitlab_client_is_branch_merged_exception(mocker):
    mocker.patch("app.clients.gitlab_client.settings.get", side_effect=lambda k, d="": "")
    client = GitLabClient()
    mock_gitlab_instance = mocker.MagicMock()
    mock_gitlab_instance.projects.get.side_effect = Exception("Not found")
    client.client = mock_gitlab_instance

    result = client.is_branch_merged("proj1", "feature/1", "release/1")
    assert result is False
