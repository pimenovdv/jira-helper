import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_unresolved_threads_reminder_task, jira_sync_task, confluence_auto_link_task, opensearch_ingestion_task, generate_release_notes_task
import app.tasks as tasks
from datetime import datetime, timezone, timedelta, timezone, timedelta
from app.tasks import gitlab_unresolved_threads_reminder_task, jira_sync_task, confluence_auto_link_task, opensearch_ingestion_task, generate_release_notes_task

@pytest.fixture(autouse=True)
def mock_astext(monkeypatch):
    from sqlalchemy.sql.elements import BinaryExpression
    monkeypatch.setattr(BinaryExpression, "astext", property(lambda self: self), raising=False)


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

@pytest.mark.asyncio
async def test_jira_sync_task_ready_for_release(mocker):
    mocker.patch('app.tasks.settings.get', side_effect=lambda k, default='': 'PROJ1' if k == 'JIRA_TRACKED_PROJECTS' else ('1' if k == 'GITLAB_TRACKED_PROJECTS' else default))

    mock_jira = mocker.patch('app.tasks.JiraClient').return_value
    mock_gl = mocker.patch('app.tasks.GitLabClient').return_value
    mocker.patch('app.tasks.Neo4jClient')

    mock_issue = mocker.MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.summary = "A Feature"
    mock_version = mocker.MagicMock()
    mock_version.name = "v1.0.0"
    mock_issue.fields.fixVersions = [mock_version]
    mock_issue.fields.status.name = "Closed" # Required for ready release

    mock_jira.search_issues.return_value = [mock_issue]

    mock_release = mocker.MagicMock()
    mock_release.name = "v1.0.0"
    mock_jira.get_project_versions.return_value = [mock_release]

    mock_branch = mocker.MagicMock()
    mock_branch.commit = {}

    mock_branch.name = "PROJ1-123"
    mock_release_branch = mocker.MagicMock()
    mock_release_branch.name = "v1.0.0"

    mock_gl.get_project_branches.return_value = [mock_branch, mock_release_branch]
    # Branch is merged
    mock_gl.is_branch_merged.return_value = True

    mock_session = mocker.AsyncMock()
    mock_session_cls = mocker.patch('app.tasks.AsyncSessionLocal')
    mock_session_cls.return_value.__aenter__.return_value = mock_session

    mock_result = mocker.MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    from app.tasks import jira_sync_task
    result = await jira_sync_task()

    assert result == "Jira sync task completed"
    # Find release event
    added_events = [call.args[0] for call in mock_session.add.call_args_list]
    release_event = next(e for e in added_events if e.event_type == "jira_release_crossmatch" and e.data["release_name"] == "v1.0.0")
    assert release_event.data["ready_for_release"] is True

@pytest.mark.asyncio
async def test_jira_sync_task_unmerged_feature(mocker):
    mocker.patch('app.tasks.settings.get', side_effect=lambda k, default='': 'PROJ1' if k == 'JIRA_TRACKED_PROJECTS' else ('1' if k == 'GITLAB_TRACKED_PROJECTS' else default))

    mock_jira = mocker.patch('app.tasks.JiraClient').return_value
    mock_gl = mocker.patch('app.tasks.GitLabClient').return_value
    mocker.patch('app.tasks.Neo4jClient')

    mock_issue = mocker.MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.summary = "A Feature"
    mock_version = mocker.MagicMock()
    mock_version.name = "v1.0.0"
    mock_issue.fields.fixVersions = [mock_version]
    mock_issue.fields.status.name = "Closed" # Required for ready release, but branch unmerged

    mock_jira.search_issues.return_value = [mock_issue]

    mock_release = mocker.MagicMock()
    mock_release.name = "v1.0.0"
    mock_jira.get_project_versions.return_value = [mock_release]

    mock_branch = mocker.MagicMock()
    mock_branch.commit = {}

    mock_branch.name = "PROJ1-123"
    mock_release_branch = mocker.MagicMock()
    mock_release_branch.name = "v1.0.0"

    mock_gl.get_project_branches.return_value = [mock_branch, mock_release_branch]
    # Branch is unmerged
    mock_gl.is_branch_merged.return_value = False

    mock_session = mocker.AsyncMock()
    mock_session_cls = mocker.patch('app.tasks.AsyncSessionLocal')
    mock_session_cls.return_value.__aenter__.return_value = mock_session

    mock_result = mocker.MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    from app.tasks import jira_sync_task
    result = await jira_sync_task()

    assert result == "Jira sync task completed"
    # Find release event
    added_events = [call.args[0] for call in mock_session.add.call_args_list]
    release_event = next(e for e in added_events if e.event_type == "jira_release_crossmatch" and e.data["release_name"] == "v1.0.0")
    assert release_event.data["ready_for_release"] is False

@pytest.mark.asyncio
async def test_confluence_auto_link_task_no_tracked_spaces(mocker):
    mocker.patch('app.tasks.JiraClient')
    mocker.patch('app.tasks.Neo4jClient')
    mocker.patch('app.tasks.settings.get', return_value='')
    from app.tasks import confluence_auto_link_task
    result = await confluence_auto_link_task()
    assert result == "Confluence auto-linking task completed"

@pytest.mark.asyncio
async def test_jira_sync_task_no_tracked_projects(mocker):
    mocker.patch('app.tasks.JiraClient')
    mocker.patch('app.tasks.Neo4jClient')
    mocker.patch('app.tasks.settings.get', return_value='')
    from app.tasks import jira_sync_task
    result = await jira_sync_task()
    assert result == "Jira sync task completed"

@pytest.mark.asyncio
async def test_gitlab_sync_task_no_tracked_projects(mocker):
    mocker.patch('app.tasks.JiraClient')
    mocker.patch('app.tasks.Neo4jClient')
    mocker.patch('app.tasks.settings.get', return_value='')
    from app.tasks import gitlab_sync_task
    result = await gitlab_sync_task()
    assert result == "GitLab sync task completed"

@pytest.mark.asyncio
async def test_gitlab_sync_task_existing_project_event(mocker):
    mocker.patch('app.tasks.settings.get', side_effect=lambda k, default='': '1' if k == 'GITLAB_TRACKED_PROJECTS' else default)
    mock_gl = mocker.patch('app.tasks.GitLabClient').return_value
    mocker.patch('app.tasks.JiraClient')
    mocker.patch('app.tasks.Neo4jClient')

    mock_event = mocker.MagicMock()
    mock_event.attributes = {"id": "123"}

    mock_gl.get_project_events.return_value = [mock_event]

    mock_session = mocker.AsyncMock()
    mock_session_cls = mocker.patch('app.tasks.AsyncSessionLocal')
    mock_session_cls.return_value.__aenter__.return_value = mock_session

    mock_result = mocker.MagicMock()
    mock_existing_event = mocker.MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_existing_event
    mock_session.execute.return_value = mock_result

    from app.tasks import gitlab_sync_task
    result = await gitlab_sync_task()

    assert result == "GitLab sync task completed"
    mock_session.add.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_sync_task_existing_user_event(mocker):
    mocker.patch('app.tasks.settings.get', side_effect=lambda k, default='': '1' if k == 'GITLAB_TRACKED_USERS' else default)
    mock_gl = mocker.patch('app.tasks.GitLabClient').return_value
    mocker.patch('app.tasks.JiraClient')
    mocker.patch('app.tasks.Neo4jClient')

    mock_event = mocker.MagicMock()
    mock_event.attributes = {"id": "123"}

    mock_gl.get_user_events.return_value = [mock_event]
    mock_gl.get_project_events.return_value = []

    mock_session = mocker.AsyncMock()
    mock_session_cls = mocker.patch('app.tasks.AsyncSessionLocal')
    mock_session_cls.return_value.__aenter__.return_value = mock_session

    mock_result = mocker.MagicMock()
    mock_existing_event = mocker.MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_existing_event
    mock_session.execute.return_value = mock_result

    from app.tasks import gitlab_sync_task
    result = await gitlab_sync_task()

    assert result == "GitLab sync task completed"
    mock_session.add.assert_not_called()

@pytest.mark.asyncio
async def test_jira_sync_task_existing_release_event_no_change(mocker):
    mocker.patch('app.tasks.settings.get', side_effect=lambda k, default='': 'PROJ1' if k == 'JIRA_TRACKED_PROJECTS' else ('1' if k == 'GITLAB_TRACKED_PROJECTS' else default))

    mock_jira = mocker.patch('app.tasks.JiraClient').return_value
    mock_gl = mocker.patch('app.tasks.GitLabClient').return_value
    mocker.patch('app.tasks.Neo4jClient')

    mock_issue = mocker.MagicMock()
    mock_issue.key = "PROJ1-123"
    mock_issue.fields.summary = "Same Feature"
    mock_issue.fields.fixVersions = []

    mock_jira.search_issues.return_value = []

    mock_release = mocker.MagicMock()
    mock_release.name = "v1.0.0"
    mock_jira.get_project_versions.return_value = [mock_release]

    mock_gl.get_project_branches.return_value = []

    mock_session = mocker.AsyncMock()
    mock_session_cls = mocker.patch('app.tasks.AsyncSessionLocal')
    mock_session_cls.return_value.__aenter__.return_value = mock_session

    mock_result = mocker.MagicMock()
    mock_existing_event = mocker.MagicMock()
    mock_existing_event.data = {
        "matched_gitlab_projects": [],
        "ready_for_release": True,
        "tasks": []
    }
    mock_result.scalar_one_or_none.return_value = mock_existing_event
    mock_session.execute.return_value = mock_result

    from app.tasks import jira_sync_task
    result = await jira_sync_task()

    assert result == "Jira sync task completed"
    mock_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_gitlab_merged_branch_cleanup_task(mocker):
    # Properly mock dynaconf settings
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default='': '1' if k == 'GITLAB_TRACKED_PROJECTS' else default
    mocker.patch('app.tasks.settings', mock_settings)

    mock_gl = mocker.patch('app.tasks.GitLabClient').return_value

    mock_merged_branch = mocker.MagicMock()
    mock_merged_branch.name = "feature-merged"
    mock_merged_branch.merged = True
    mock_merged_branch.protected = False
    mock_merged_branch.default = False

    mock_unmerged_branch = mocker.MagicMock()
    mock_unmerged_branch.name = "feature-active"
    mock_unmerged_branch.merged = False
    mock_unmerged_branch.protected = False
    mock_unmerged_branch.default = False

    mock_protected_branch = mocker.MagicMock()
    mock_protected_branch.name = "main"
    mock_protected_branch.merged = True
    mock_protected_branch.protected = True
    mock_protected_branch.default = True

    mock_gl.get_project_branches.return_value = [
        mock_merged_branch,
        mock_unmerged_branch,
        mock_protected_branch
    ]
    mock_gl.delete_branch.return_value = True

    from app.tasks import gitlab_merged_branch_cleanup_task
    await gitlab_merged_branch_cleanup_task()

    mock_gl.delete_branch.assert_called_once_with("1", "feature-merged")


@pytest.mark.asyncio
async def test_gitlab_mr_conflict_notifier_task_has_conflict(mocker):
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default='': '1' if k == 'GITLAB_TRACKED_PROJECTS' else 'test_key' if k == 'OPENAI_API_KEY' else default
    mocker.patch('app.tasks.settings', mock_settings)

    mock_gl_client = mocker.patch('app.tasks.GitLabClient').return_value
    mock_llm_instance = mocker.MagicMock()

    class MockResponse:
        content = "Resolve your conflicts!"

    mock_llm_instance.ainvoke = mocker.AsyncMock(return_value=MockResponse())
    mocker.patch('app.tasks.ChatOpenAI', return_value=mock_llm_instance)


    mock_mr = mocker.MagicMock()
    mock_mr.title = "Test MR"
    mock_mr.iid = 42
    mock_mr.has_conflicts = True

    mock_note = mocker.MagicMock()
    mock_note.body = "Just a regular note"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project = mocker.MagicMock()
    mock_project.mergerequests.list.return_value = [mock_mr]
    mock_gl_client.client.projects.get.return_value = mock_project

    from app.tasks import gitlab_mr_conflict_notifier_task
    result = await gitlab_mr_conflict_notifier_task()

    assert "completed" in result
    mock_gl_client.create_mr_note.assert_called_once_with('1', 42, "Resolve your conflicts!")


@pytest.mark.asyncio
async def test_gitlab_mr_conflict_notifier_task_no_conflict(mocker):
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default='': '1' if k == 'GITLAB_TRACKED_PROJECTS' else 'test_key' if k == 'OPENAI_API_KEY' else default
    mocker.patch('app.tasks.settings', mock_settings)

    mock_gl_client = mocker.patch('app.tasks.GitLabClient').return_value
    mocker.patch('app.tasks.ChatOpenAI')

    mock_mr = mocker.MagicMock()
    mock_mr.has_conflicts = False

    mock_project = mocker.MagicMock()
    mock_project.mergerequests.list.return_value = [mock_mr]
    mock_gl_client.client.projects.get.return_value = mock_project

    from app.tasks import gitlab_mr_conflict_notifier_task
    result = await gitlab_mr_conflict_notifier_task()

    assert "completed" in result
    mock_gl_client.create_mr_note.assert_not_called()


@pytest.mark.asyncio
async def test_gitlab_mr_conflict_notifier_task_already_notified(mocker):
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default='': '1' if k == 'GITLAB_TRACKED_PROJECTS' else 'test_key' if k == 'OPENAI_API_KEY' else default
    mocker.patch('app.tasks.settings', mock_settings)

    mock_gl_client = mocker.patch('app.tasks.GitLabClient').return_value
    mocker.patch('app.tasks.ChatOpenAI')

    mock_mr = mocker.MagicMock()
    mock_mr.has_conflicts = True

    mock_note = mocker.MagicMock()
    mock_note.body = "<!-- AUTO_GENERATED_MR_CONFLICT_NOTIFIER --> previous reminder"
    mock_mr.notes.list.return_value = [mock_note]

    mock_project = mocker.MagicMock()
    mock_project.mergerequests.list.return_value = [mock_mr]
    mock_gl_client.client.projects.get.return_value = mock_project

    from app.tasks import gitlab_mr_conflict_notifier_task
    result = await gitlab_mr_conflict_notifier_task()

    assert "completed" in result
    mock_gl_client.create_mr_note.assert_not_called()

@pytest.mark.asyncio
async def test_gitlab_empty_mr_description_notifier_task(mocker):
    from app.tasks import gitlab_empty_mr_description_notifier_task

    # Mock settings
    def mock_settings_get(key, default=""):
        if key == "GITLAB_TRACKED_PROJECTS":
            return "1"
        elif key == "OPENAI_API_KEY":
            return "test_key"
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)

    # Mock ChatOpenAI
    mock_llm_cls = mocker.patch('app.tasks.ChatOpenAI')
    mock_llm = mock_llm_cls.return_value
    mock_response = mocker.MagicMock()
    mock_response.content = "Please add a description. <!-- AUTO_GENERATED_EMPTY_MR_DESCRIPTION_NOTIFIER -->"
    mock_llm.ainvoke = mocker.AsyncMock(return_value=mock_response)

    # Mock GitLabClient
    mock_gitlab_client_cls = mocker.patch('app.tasks.GitLabClient')

    # Notice that client instantiation within the task looks like:
    # client = GitLabClient()
    # project = client.client.projects.get(project_id)

    mock_gitlab = mock_gitlab_client_cls.return_value
    mock_gitlab_inner = mocker.MagicMock()
    mock_gitlab.client = mock_gitlab_inner

    # Setup project and MR
    mock_project = mocker.MagicMock()
    mock_gitlab_inner.projects.get.return_value = mock_project

    mock_mr = mocker.MagicMock()
    mock_mr.iid = 101
    mock_mr.title = "Test MR"
    mock_mr.description = "short" # less than 10 characters
    mock_project.mergerequests.list.return_value = [mock_mr]

    # MR has no existing notes
    mock_mr.notes.list.return_value = []

    # Run the task
    result = await gitlab_empty_mr_description_notifier_task()

    assert result == "GitLab empty MR description notifier task completed"

    # Assert LLM was called
    mock_llm.ainvoke.assert_called_once()

    # Assert client.create_mr_note was called
    mock_gitlab.create_mr_note.assert_called_once_with(
        "1", 101, "Please add a description. <!-- AUTO_GENERATED_EMPTY_MR_DESCRIPTION_NOTIFIER -->"
    )

@pytest.mark.asyncio
async def test_gitlab_empty_mr_description_notifier_task_long_description(mocker):
    from app.tasks import gitlab_empty_mr_description_notifier_task

    # Mock settings
    def mock_settings_get(key, default=""):
        if key == "GITLAB_TRACKED_PROJECTS":
            return "1"
        elif key == "OPENAI_API_KEY":
            return "test_key"
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)

    # Mock ChatOpenAI
    mock_llm_cls = mocker.patch('app.tasks.ChatOpenAI')
    mock_llm = mock_llm_cls.return_value

    # Mock GitLabClient
    mock_gitlab_client_cls = mocker.patch('app.tasks.GitLabClient')

    # Notice that client instantiation within the task looks like:
    # client = GitLabClient()
    # project = client.client.projects.get(project_id)

    mock_gitlab = mock_gitlab_client_cls.return_value
    mock_gitlab_inner = mocker.MagicMock()
    mock_gitlab.client = mock_gitlab_inner

    # Setup project and MR
    mock_project = mocker.MagicMock()
    mock_gitlab_inner.projects.get.return_value = mock_project

    mock_mr = mocker.MagicMock()
    mock_mr.iid = 101
    mock_mr.title = "Test MR"
    mock_mr.description = "This is a proper description that is longer than 10 characters."
    mock_project.mergerequests.list.return_value = [mock_mr]

    # Run the task
    result = await gitlab_empty_mr_description_notifier_task()

    assert result == "GitLab empty MR description notifier task completed"

    # Assert LLM was NOT called
    mock_llm.ainvoke.assert_not_called()

    # Assert client.create_mr_note was NOT called
    mock_gitlab.create_mr_note.assert_not_called()

@pytest.fixture
def mock_settings(mocker):
    mock = MagicMock()
    mock.get.side_effect = lambda k, default="": "fake_key" if k == "OPENAI_API_KEY" else "123" if k == "GITLAB_TRACKED_PROJECTS" else default
    mocker.patch.object(tasks, 'settings', mock)
    return mock

@pytest.mark.asyncio
async def test_gitlab_unresolved_threads_reminder_task(mocker, mock_settings):
    # Mock LLM
    mock_llm_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Reminder comment"
    mock_llm_instance.ainvoke = mocker.AsyncMock(return_value=mock_response)
    mock_chat_openai = mocker.patch.object(tasks, 'ChatOpenAI', return_value=mock_llm_instance)

    # Mock GitLab
    mock_gitlab_client_class = mocker.patch.object(tasks, 'GitLabClient')
    mock_client_instance = mock_gitlab_client_class.return_value
    mock_project = MagicMock()
    mock_client_instance.client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.title = "Test MR"
    mock_mr.iid = 1
    mock_project.mergerequests.list.return_value = [mock_mr]

    # Create a discussion with notes
    mock_discussion = MagicMock()
    # 4 days ago
    past_date = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
    mock_discussion.attributes = {
        'notes': [
            {
                'resolvable': True,
                'resolved': False,
                'updated_at': past_date,
                'body': 'First note'
            }
        ]
    }

    mock_mr.discussions.list.return_value = [mock_discussion]

    # Run task
    result = await gitlab_unresolved_threads_reminder_task()

    assert result == "GitLab unresolved threads reminder task completed"
    mock_discussion.notes.create.assert_called_once_with({'body': 'Reminder comment'})
    assert mock_llm_instance.ainvoke.call_count == 1

    # Test skipping logic - already reminded
    mock_discussion.notes.create.reset_mock()
    mock_llm_instance.ainvoke.reset_mock()

    mock_discussion.attributes['notes'].append({
        'body': '<!-- AUTO_GENERATED_UNRESOLVED_THREAD_REMINDER -->'
    })

    await gitlab_unresolved_threads_reminder_task()
    mock_discussion.notes.create.assert_not_called()
    mock_llm_instance.invoke.assert_not_called()

@pytest.fixture
def mock_settings(mocker):
    mock = MagicMock()
    mock.get.side_effect = lambda k, default="": "fake_key" if k == "OPENAI_API_KEY" else "123" if k == "GITLAB_TRACKED_PROJECTS" else default
    mocker.patch.object(tasks, 'settings', mock)
    return mock

@pytest.mark.asyncio
async def test_gitlab_unresolved_threads_reminder_task(mocker, mock_settings):
    # Mock LLM
    mock_llm_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Reminder comment"
    mock_llm_instance.ainvoke = mocker.AsyncMock(return_value=mock_response)
    mock_chat_openai = mocker.patch.object(tasks, 'ChatOpenAI', return_value=mock_llm_instance)

    # Mock GitLab
    mock_gitlab_client_class = mocker.patch.object(tasks, 'GitLabClient')
    mock_client_instance = mock_gitlab_client_class.return_value
    mock_project = MagicMock()
    mock_client_instance.client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.title = "Test MR"
    mock_mr.iid = 1
    mock_project.mergerequests.list.return_value = [mock_mr]

    # Create a discussion with notes
    mock_discussion = MagicMock()
    # 4 days ago
    past_date = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
    mock_discussion.attributes = {
        'notes': [
            {
                'resolvable': True,
                'resolved': False,
                'updated_at': past_date,
                'body': 'First note'
            }
        ]
    }

    mock_mr.discussions.list.return_value = [mock_discussion]

    # Run task
    result = await gitlab_unresolved_threads_reminder_task()

    assert result == "GitLab unresolved threads reminder task completed"
    mock_discussion.notes.create.assert_called_once_with({'body': 'Reminder comment'})
    assert mock_llm_instance.ainvoke.call_count == 1

    # Test skipping logic - already reminded
    mock_discussion.notes.create.reset_mock()
    mock_llm_instance.ainvoke.reset_mock()

    mock_discussion.attributes['notes'].append({
        'body': '<!-- AUTO_GENERATED_UNRESOLVED_THREAD_REMINDER -->'
    })

    await gitlab_unresolved_threads_reminder_task()
    mock_discussion.notes.create.assert_not_called()
    mock_llm_instance.invoke.assert_not_called()


@pytest.mark.asyncio
async def test_gitlab_unresolved_threads_reminder_task(mocker):
    # Mock settings
    def mock_settings_get(key, default=""):
        if key == "GITLAB_TRACKED_PROJECTS":
            return "123"
        elif key == "OPENAI_API_KEY":
            return "fake_key"
        return default

    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = mock_settings_get
    mocker.patch('app.tasks.settings', mock_settings)

    # Mock LLM
    mock_llm_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Reminder comment"
    mock_llm_instance.ainvoke = mocker.AsyncMock(return_value=mock_response)
    mocker.patch('app.tasks.ChatOpenAI', return_value=mock_llm_instance)


    # Mock GitLab
    mock_gitlab_client_class = mocker.patch('app.tasks.GitLabClient')
    mock_client_instance = mock_gitlab_client_class.return_value
    mock_project = MagicMock()
    mock_client_instance.client.projects.get.return_value = mock_project

    mock_mr = MagicMock()
    mock_mr.title = "Test MR"
    mock_mr.iid = 1
    mock_project.mergerequests.list.return_value = [mock_mr]

    # Create a discussion with notes
    mock_discussion = MagicMock()
    # 4 days ago
    past_date = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
    mock_discussion.attributes = {
        'notes': [
            {
                'resolvable': True,
                'resolved': False,
                'updated_at': past_date,
                'body': 'First note'
            }
        ]
    }

    mock_mr.discussions.list.return_value = [mock_discussion]

    # Run task
    result = await gitlab_unresolved_threads_reminder_task()

    assert result == "GitLab unresolved threads reminder task completed"
    mock_discussion.notes.create.assert_called_once_with({'body': 'Reminder comment'})
    assert mock_llm_instance.ainvoke.call_count == 1

    # Test skipping logic - already reminded
    mock_discussion.notes.create.reset_mock()
    mock_llm_instance.ainvoke.reset_mock()

    mock_discussion.attributes['notes'].append({
        'body': '<!-- AUTO_GENERATED_UNRESOLVED_THREAD_REMINDER -->'
    })

    await gitlab_unresolved_threads_reminder_task()
    mock_discussion.notes.create.assert_not_called()
    mock_llm_instance.invoke.assert_not_called()
import pytest
from app.tasks import jira_sprint_unassigned_task_reminder_task

@pytest.mark.asyncio
async def test_jira_sprint_unassigned_task_reminder(mocker):
    # Mock settings to return a test project and dummy API key
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default="": "PROJ" if k == "JIRA_TRACKED_PROJECTS" else ("dummy_key" if k == "OPENAI_API_KEY" else default)
    mocker.patch('app.tasks.settings', mock_settings)

    # Mock LLM
    mock_llm_instance = mocker.MagicMock()
    mock_llm_response = mocker.MagicMock()
    mock_llm_response.content = "Please assign this task."
    mock_llm_instance.invoke.return_value = mock_llm_response
    mocker.patch('app.tasks.ChatOpenAI', return_value=mock_llm_instance)


    # Mock JiraClient class completely to avoid actual initialization
    mock_jira_client_cls = mocker.patch('app.tasks.JiraClient')
    mock_jira_client = mock_jira_client_cls.return_value
    mock_issue = mocker.MagicMock()
    mock_issue.key = "PROJ-123"
    mock_jira_client.search_issues.return_value = [mock_issue]

    # No existing comments
    mock_jira_client.get_comments.return_value = []

    result = await jira_sprint_unassigned_task_reminder_task()

    assert result == "Jira sprint unassigned task reminder task completed"
    mock_jira_client.search_issues.assert_any_call('project = "PROJ" AND sprint in openSprints() AND assignee IS EMPTY AND statusCategory != Done')
    mock_llm_instance.invoke.assert_called_once()
    mock_jira_client.add_comment.assert_called_once()
    assert "Please assign this task." in mock_jira_client.add_comment.call_args[0][1]
    assert "<!-- AUTO_GENERATED_JIRA_SPRINT_UNASSIGNED_TASK_REMINDER -->" in mock_jira_client.add_comment.call_args[0][1]


@pytest.mark.asyncio
async def test_jira_sprint_unassigned_task_reminder_already_notified(mocker):
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default="": "PROJ" if k == "JIRA_TRACKED_PROJECTS" else ("dummy_key" if k == "OPENAI_API_KEY" else default)
    mocker.patch('app.tasks.settings', mock_settings)

    mock_llm_instance = mocker.MagicMock()
    mocker.patch('app.tasks.ChatOpenAI', return_value=mock_llm_instance)


    mock_jira_client_cls = mocker.patch('app.tasks.JiraClient')
    mock_jira_client = mock_jira_client_cls.return_value
    mock_issue = mocker.MagicMock()
    mock_issue.key = "PROJ-123"
    mock_jira_client.search_issues.return_value = [mock_issue]

    # Existing comment with the marker
    mock_comment = mocker.MagicMock()
    mock_comment.body = "Some comment\n<!-- AUTO_GENERATED_JIRA_SPRINT_UNASSIGNED_TASK_REMINDER -->"
    mock_jira_client.get_comments.return_value = [mock_comment]

    result = await jira_sprint_unassigned_task_reminder_task()

    assert result == "Jira sprint unassigned task reminder task completed"
    mock_llm_instance.invoke.assert_not_called()
    mock_jira_client.add_comment.assert_not_called()


@pytest.mark.asyncio
async def test_jira_sprint_unassigned_task_reminder_no_api_key(mocker):
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default="": "PROJ" if k == "JIRA_TRACKED_PROJECTS" else ("" if k == "OPENAI_API_KEY" else default)
    mocker.patch('app.tasks.settings', mock_settings)

    mock_jira_client_cls = mocker.patch('app.tasks.JiraClient')

    result = await jira_sprint_unassigned_task_reminder_task()

    assert result == "Jira sprint unassigned task reminder task skipped (no OpenAI API key)"
    mock_jira_client_cls.assert_not_called()

@pytest.mark.asyncio
async def test_jira_missing_fixversion_reminder_task(mocker):
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default="": "TLA" if k == "JIRA_TRACKED_PROJECTS" else ("fake_key" if k == "OPENAI_API_KEY" else default)
    mocker.patch('app.tasks.settings', mock_settings)

    mock_llm_instance = mocker.MagicMock()
    mock_llm_response = mocker.MagicMock()
    mock_llm_response.content = "Please add a fixVersion."
    mock_llm_instance.invoke.return_value = mock_llm_response
    mocker.patch('app.tasks.ChatOpenAI', return_value=mock_llm_instance)

    mock_jira_client_cls = mocker.patch('app.tasks.JiraClient')
    mock_jira_client = mock_jira_client_cls.return_value
    mock_issue = mocker.MagicMock()
    mock_issue.key = "TLA-123"
    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_comment1 = mocker.MagicMock()
    mock_comment1.body = "Some normal comment"
    mock_jira_client.get_comments.return_value = [mock_comment1]

    from app.tasks import jira_missing_fixversion_reminder_task
    result = await jira_missing_fixversion_reminder_task()

    assert result == "Jira missing fixVersion reminder task completed"
    mock_jira_client.search_issues.assert_called_once_with('project = "TLA" AND statusCategory = Done AND fixVersion is EMPTY')
    mock_llm_instance.invoke.assert_called_once()
    mock_jira_client.add_comment.assert_called_once_with("TLA-123", "Please add a fixVersion.\n\n<!-- AUTO_GENERATED_JIRA_MISSING_FIXVERSION_REMINDER -->")

@pytest.mark.asyncio
async def test_jira_missing_fixversion_reminder_task_already_reminded(mocker):
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default="": "TLA" if k == "JIRA_TRACKED_PROJECTS" else ("fake_key" if k == "OPENAI_API_KEY" else default)
    mocker.patch('app.tasks.settings', mock_settings)

    mock_llm_instance = mocker.MagicMock()
    mocker.patch("app.tasks.ChatOpenAI", return_value=mock_llm_instance)

    mock_jira_client_cls = mocker.patch('app.tasks.JiraClient')
    mock_jira_client = mock_jira_client_cls.return_value
    mock_issue = mocker.MagicMock()
    mock_issue.key = "TLA-123"
    mock_jira_client.search_issues.return_value = [mock_issue]

    mock_comment1 = mocker.MagicMock()
    mock_comment1.body = "<!-- AUTO_GENERATED_JIRA_MISSING_FIXVERSION_REMINDER -->"
    mock_jira_client.get_comments.return_value = [mock_comment1]

    from app.tasks import jira_missing_fixversion_reminder_task
    result = await jira_missing_fixversion_reminder_task()

    assert result == "Jira missing fixVersion reminder task completed"
    mock_llm_instance.invoke.assert_not_called()
    mock_jira_client.add_comment.assert_not_called()

@pytest.mark.asyncio
async def test_jira_missing_fixversion_reminder_task_no_api_key(mocker):
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, default="": "" if k == "OPENAI_API_KEY" else default
    mocker.patch("app.tasks.settings", mock_settings)

    from app.tasks import jira_missing_fixversion_reminder_task
    result = await jira_missing_fixversion_reminder_task()
    assert result == "Jira missing fixVersion reminder task skipped (no OpenAI API key)"
