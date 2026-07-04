import app.tasks
import pytest

@pytest.fixture(autouse=True)
def mock_astext(monkeypatch):
    from sqlalchemy.sql.elements import BinaryExpression
    monkeypatch.setattr(BinaryExpression, "astext", property(lambda self: self), raising=False)

from unittest.mock import MagicMock
from app.tasks import jira_sync_task

@pytest.mark.asyncio
async def test_jira_sync_task(mocker):
    # Mock settings
    def mock_settings_get(key, default=""):
        if key == "GITLAB_TRACKED_PROJECTS":
            return "1, 2"
        elif key == "JIRA_TRACKED_PROJECTS":
            return "PROJ1"
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)


    # Mock GitLabClient
    mock_gitlab_client_cls = mocker.patch('app.tasks.GitLabClient')
    mock_gitlab = mock_gitlab_client_cls.return_value

    mock_branch_1 = MagicMock()
    mock_branch_1.name = "feature/PROJ1-123-new-feature"
    mock_branch_2 = MagicMock()
    mock_branch_2.name = "release/v1.0.0"

    mock_branch_3 = MagicMock()
    mock_branch_3.name = "fix/PROJ1-456-bug"

    # Project 1 branches
    # Project 2 branches
    mock_gitlab.get_project_branches.side_effect = lambda pid: [mock_branch_1, mock_branch_2] if pid == "1" else [mock_branch_3]

    # Mock JiraClient
    mock_jira_client_cls = mocker.patch('app.tasks.JiraClient')
    mock_jira = mock_jira_client_cls.return_value

    mock_issue_1 = MagicMock()
    mock_issue_1.key = "PROJ1-123"
    mock_issue_1.fields.summary = "New Feature"
    mock_version = MagicMock()
    mock_version.name = "v1.0.0"
    mock_issue_1.fields.fixVersions = [mock_version]

    mock_issue_2 = MagicMock()
    mock_issue_2.key = "PROJ1-456"
    mock_issue_2.fields.summary = "Bug Fix"

    mock_issue_3 = MagicMock()
    mock_issue_3.key = "PROJ1-789"
    mock_issue_3.fields.summary = "Unrelated"

    mock_jira.search_issues.return_value = [mock_issue_1, mock_issue_2, mock_issue_3]

    mock_release_1 = MagicMock()
    mock_release_1.name = "v1.0.0"
    mock_release_1.projectId = "10000"
    mock_jira.get_project_versions.return_value = [mock_release_1]

    # Mock Neo4jClient
    mock_neo4j_client_cls = mocker.patch('app.tasks.Neo4jClient')
    mock_neo4j = mock_neo4j_client_cls.return_value

    # Mock AsyncSessionLocal and database operations
    mock_session = mocker.AsyncMock()
    mock_session.add = mocker.MagicMock()
    mock_session_cls = mocker.patch('app.tasks.AsyncSessionLocal')
    mock_session_cls.return_value.__aenter__.return_value = mock_session

    # Mock execute for checking existing events (assume none exist)
    mock_result = mocker.MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    # Run the task
    result = await jira_sync_task()
    assert result == "Jira sync task completed"

    # Verify cross-match logic by checking session.add calls
    # Should save: PROJ1-123 (proj 1), PROJ1-456 (proj 2), v1.0.0 (proj 1)
    # Total 3 add calls

    for call in mock_session.add.call_args_list:
        e = call.args[0]
        print(f"EVENT ADDED: {e.event_type} - {e.data}")
    assert mock_session.add.call_count == 4


    added_events = [call.args[0] for call in mock_session.add.call_args_list]

    # Check first task crossmatch
    task_1_event = next(e for e in added_events if e.event_type == "jira_task_crossmatch" and e.data["task_id"] == "PROJ1-123")
    assert task_1_event.data["matched_gitlab_projects"] == ["1"]

    # Check second task crossmatch
    task_2_event = next(e for e in added_events if e.event_type == "jira_task_crossmatch" and e.data["task_id"] == "PROJ1-456")
    assert task_2_event.data["matched_gitlab_projects"] == ["2"]

    # Check release crossmatch
    release_event = next(e for e in added_events if e.event_type == "jira_release_crossmatch" and e.data["release_name"] == "v1.0.0")
    assert release_event.data["matched_gitlab_projects"] == ["1"]
    assert "ready_for_release" in release_event.data
    assert "tasks" in release_event.data

    mock_session.commit.assert_called_once()

    # Verify Neo4jClient interactions
    mock_neo4j.link_task_to_project.assert_any_call("PROJ1-123", "1")
    mock_neo4j.link_task_to_project.assert_any_call("PROJ1-456", "2")
    assert mock_neo4j.link_task_to_project.call_count == 2

    mock_neo4j.link_release_to_project.assert_called_once_with("v1.0.0", "1")


from app.tasks import confluence_auto_link_task

@pytest.mark.asyncio
async def test_confluence_auto_link_task(mocker):
    # Mock settings
    def mock_settings_get(key, default=""):
        if key == "GITLAB_TRACKED_PROJECTS":
            return "1, 2"
        elif key == "CONFLUENCE_TRACKED_SPACES":
            return "SPACE1"
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)

    # Mock GitLabClient
    mock_gitlab_client_cls = mocker.patch('app.tasks.GitLabClient')
    mock_gitlab = mock_gitlab_client_cls.return_value

    mock_proj_1 = MagicMock()
    mock_proj_1.name = "AwesomeProject"

    mock_proj_2 = MagicMock()
    mock_proj_2.name = "OtherProject"

    mock_gitlab.get_project.side_effect = lambda pid: mock_proj_1 if pid == "1" else mock_proj_2

    # Mock ConfluenceClient
    mock_confluence_client_cls = mocker.patch('app.tasks.ConfluenceClient')
    mock_confluence = mock_confluence_client_cls.return_value

    mock_page_1 = {"id": "123", "title": "Design Doc for AwesomeProject"}
    mock_page_2 = {"id": "456", "title": "Random meeting notes"}

    mock_confluence.client.get_all_pages_from_space.return_value = [mock_page_1, mock_page_2]

    # Mock DB
    mock_session = mocker.AsyncMock()
    mock_session.add = mocker.MagicMock()
    mock_session_cls = mocker.patch('app.tasks.AsyncSessionLocal')
    mock_session_cls.return_value.__aenter__.return_value = mock_session

    mock_result = mocker.MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await confluence_auto_link_task()
    assert result == "Confluence auto-linking task completed"

    assert mock_session.add.call_count == 1
    added_event = mock_session.add.call_args[0][0]

    assert added_event.event_type == "confluence_project_link"
    assert added_event.data["page_id"] == "123"
    assert added_event.data["auto_linked_projects"] == ["1"]

    mock_session.commit.assert_called_once()

from app.tasks import opensearch_ingestion_task

def test_opensearch_ingestion_task(mocker):
    # Mock settings
    def mock_settings_get(key, default=""):
        if key == "CONFLUENCE_TRACKED_SPACES":
            return "SPACE1"
        elif key == "OPENAI_API_KEY":
            return "test_openai_key"
        elif key == "OPENSEARCH_URL":
            return "http://localhost:9200"
        elif key == "OPENSEARCH_USER":
            return "admin"
        elif key == "OPENSEARCH_PASSWORD":
            return "admin"
        elif key == "OPENSEARCH_VERIFY_CERTS":
            return False
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)

    # Mock ConfluenceClient
    mock_confluence_client_cls = mocker.patch('app.tasks.ConfluenceClient')
    mock_confluence = mock_confluence_client_cls.return_value

    mock_page_1 = {
        "id": "123",
        "title": "Design Doc",
        "body": {
            "storage": {
                "value": "<p>This is a test doc.</p>"
            }
        }
    }

    mock_confluence.client.get_all_pages_from_space.return_value = [mock_page_1]

    # Mock OpenAIEmbeddings
    mocker.patch('app.tasks.OpenAIEmbeddings')

    # Mock OpenSearchVectorSearch
    mock_os_search = mocker.patch('app.tasks.OpenSearchVectorSearch')

    result = opensearch_ingestion_task()
    assert result == "OpenSearch ingestion task completed"
    mock_os_search.from_documents.assert_called_once()

from app.tasks import generate_release_notes_task

def test_generate_release_notes_task(mocker):
    # Mock settings
    def mock_settings_get(key, default=""):
        if key == "JIRA_TRACKED_PROJECTS":
            return "PROJ1"
        elif key == "CONFLUENCE_TRACKED_SPACES":
            return "SPACE1"
        elif key == "OPENAI_API_KEY":
            return "test_openai_key"
        elif key == "OPENSEARCH_URL":
            return "http://localhost:9200"
        elif key == "OPENSEARCH_USER":
            return "admin"
        elif key == "OPENSEARCH_PASSWORD":
            return "admin"
        elif key == "OPENSEARCH_VERIFY_CERTS":
            return False
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)

    # Mock JiraClient
    mock_jira_client_cls = mocker.patch('app.tasks.JiraClient')
    mock_jira = mock_jira_client_cls.return_value

    mock_release = mocker.MagicMock()
    mock_release.name = "v1.0.0"
    mock_jira.get_project_versions.return_value = [mock_release]

    mock_issue = mocker.MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.summary = "Test Issue"
    mock_version = mocker.MagicMock()
    mock_version.name = "v1.0.0"
    mock_issue.fields.fixVersions = [mock_version]
    mock_jira.search_issues.return_value = [mock_issue]

    # Mock ConfluenceClient
    mock_confluence_client_cls = mocker.patch('app.tasks.ConfluenceClient')
    mock_confluence = mock_confluence_client_cls.return_value
    mock_confluence.client.create_page = mocker.MagicMock()

    # Mock Embeddings and OpenSearch
    mocker.patch('app.tasks.OpenAIEmbeddings')
    mock_os_search = mocker.patch('app.tasks.OpenSearchVectorSearch')
    mock_retriever = mocker.MagicMock()
    mock_doc = mocker.MagicMock()
    mock_doc.page_content = "Context for PROJ1-123."
    mock_retriever.invoke.return_value = [mock_doc]
    mock_os_search.return_value.as_retriever.return_value = mock_retriever

    # Mock ChatOpenAI
    mock_chat_openai_cls = mocker.patch('app.tasks.ChatOpenAI')
    mock_chat_instance = mock_chat_openai_cls.return_value
    # PromptTemplate | LLM chain mock logic
    mock_chain = mocker.MagicMock()
    mock_response = mocker.MagicMock()
    mock_response.content = "<p>Draft release notes for v1.0.0</p>"
    mock_chain.invoke.return_value = mock_response

    # Need to mock the chain creation
    # ChatPromptTemplate.from_template() returns a template
    # template | llm returns a chain
    mock_prompt_template_cls = mocker.patch('app.tasks.ChatPromptTemplate')
    mock_prompt_template = mock_prompt_template_cls.from_template.return_value
    mock_prompt_template.__or__.return_value = mock_chain

    # Run the task
    result = generate_release_notes_task()

    assert result == "Release notes task completed"

    # Verify Confluence create_page was called correctly
    mock_confluence.client.create_page.assert_called_once_with(
        space="SPACE1",
        title="Release Notes v1.0.0",
        body="<p>Draft release notes for v1.0.0</p>",
        parent_id=None
    )
