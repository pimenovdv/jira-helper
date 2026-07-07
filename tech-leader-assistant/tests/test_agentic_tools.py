import pytest
from unittest.mock import patch, MagicMock

from app.tools.agentic_tools import (
    query_jira,
    search_gitlab_projects,
    get_gitlab_commits,
    query_gitlab_mrs,
    query_confluence,
    search_technical_docs
)

@patch("app.tools.agentic_tools.JiraClient")
def test_query_jira(mock_jira_client_class):
    mock_jira = MagicMock()
    mock_jira_client_class.return_value = mock_jira

    mock_issue = MagicMock()
    mock_issue.key = "TLA-123"
    mock_issue.fields.summary = "Test issue"
    mock_issue.fields.status.name = "In Progress"
    mock_issue.fields.assignee.displayName = "John Doe"
    mock_issue.fields.description = "Test description"
    mock_jira.search_issues.return_value = [mock_issue]

    result = query_jira.invoke({"jql": "project=TLA"})
    assert len(result) == 1
    assert result[0]["key"] == "TLA-123"
    assert result[0]["summary"] == "Test issue"
    assert result[0]["status"] == "In Progress"
    assert result[0]["assignee"] == "John Doe"
    assert result[0]["description"] == "Test description"
    mock_jira.search_issues.assert_called_once_with("project=TLA")

@patch("app.tools.agentic_tools.GitLabClient")
def test_search_gitlab_projects(mock_gitlab_client_class):
    mock_gl = MagicMock()
    mock_gitlab_client_class.return_value = mock_gl

    mock_proj = MagicMock()
    mock_proj.id = 1
    mock_proj.name = "backend"
    mock_proj.path_with_namespace = "org/backend"
    mock_proj.description = "Backend repo"
    mock_gl.search_projects.return_value = [mock_proj]

    result = search_gitlab_projects.invoke({"query": "backend"})
    assert len(result) == 1
    assert result[0]["id"] == 1
    assert result[0]["name"] == "backend"
    mock_gl.search_projects.assert_called_once_with("backend")

@patch("app.tools.agentic_tools.GitLabClient")
def test_get_gitlab_commits(mock_gitlab_client_class):
    mock_gl = MagicMock()
    mock_gitlab_client_class.return_value = mock_gl

    mock_commit = MagicMock()
    mock_commit.id = "abcdef"
    mock_commit.title = "Fix bug"
    mock_commit.author_name = "Alice"
    mock_commit.created_at = "2023-01-01T12:00:00Z"
    mock_commit.message = "Fix bug in auth"
    mock_gl.get_project_commits.return_value = [mock_commit]

    result = get_gitlab_commits.invoke({"project_id": "1"})
    assert len(result) == 1
    assert result[0]["id"] == "abcdef"
    mock_gl.get_project_commits.assert_called_once_with("1")

@patch("app.tools.agentic_tools.GitLabClient")
def test_query_gitlab_mrs(mock_gitlab_client_class):
    mock_gl = MagicMock()
    mock_gitlab_client_class.return_value = mock_gl

    mock_mr = MagicMock()
    mock_mr.id = 101
    mock_mr.iid = 2
    mock_mr.title = "Add feature"
    mock_mr.state = "opened"
    mock_mr.author = {"name": "Bob"}
    mock_mr.source_branch = "feature-x"
    mock_mr.target_branch = "main"
    mock_gl.get_project_merge_requests.return_value = [mock_mr]

    result = query_gitlab_mrs.invoke({"project_id": "1", "state": "opened"})
    assert len(result) == 1
    assert result[0]["id"] == 101
    assert result[0]["author"] == "Bob"
    mock_gl.get_project_merge_requests.assert_called_once_with("1", state="opened")

@patch("app.tools.agentic_tools.ConfluenceClient")
def test_query_confluence(mock_confluence_client_class):
    mock_conf = MagicMock()
    mock_confluence_client_class.return_value = mock_conf

    mock_conf.search_cql.return_value = {
        "results": [
            {
                "content": {
                    "title": "Architecture",
                    "id": "12345",
                    "type": "page",
                    "_links": {"webui": "/pages/12345"}
                },
                "excerpt": "Describes architecture."
            }
        ]
    }

    result = query_confluence.invoke({"cql": "title~Architecture"})
    assert len(result) == 1
    assert result[0]["title"] == "Architecture"
    assert result[0]["id"] == "12345"
    mock_conf.search_cql.assert_called_once_with("title~Architecture")

@patch("app.tools.agentic_tools.OpenSearchVectorSearch")
@patch("app.tools.agentic_tools.OpenAIEmbeddings")
def test_search_technical_docs(mock_embeddings, mock_vector_search):
    mock_vs_instance = MagicMock()
    mock_vector_search.return_value = mock_vs_instance

    mock_retriever = MagicMock()
    mock_vs_instance.as_retriever.return_value = mock_retriever

    mock_doc = MagicMock()
    mock_doc.page_content = "Technical details here."
    mock_retriever.invoke.return_value = [mock_doc]

    result = search_technical_docs.invoke({"query": "architecture"})
    assert len(result) == 1
    assert result[0] == "Technical details here."
    mock_retriever.invoke.assert_called_once_with("architecture")
