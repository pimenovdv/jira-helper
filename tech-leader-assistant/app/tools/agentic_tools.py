from langchain_core.tools import tool
from typing import List, Dict, Any
from app.clients import JiraClient, GitLabClient, ConfluenceClient
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import OpenSearchVectorSearch
from app.clients import settings

@tool
def query_jira(jql: str) -> List[Dict[str, Any]]:
    """
    Выполняет JQL запрос к Jira для поиска задач, их статусов, спринтов и комментариев.
    Используйте этот инструмент, когда нужно получить актуальную информацию о задачах из Jira (например, статус задачи, описание, кто назначен).
    """
    jira_client = JiraClient()
    issues = jira_client.search_issues(jql)

    result = []
    for issue in issues:
        result.append({
            "key": issue.key,
            "summary": getattr(issue.fields, "summary", ""),
            "status": getattr(issue.fields.status, "name", "") if hasattr(issue.fields, "status") else "",
            "assignee": getattr(issue.fields.assignee, "displayName", "") if getattr(issue.fields, "assignee", None) else "",
            "description": getattr(issue.fields, "description", "")
        })
    return result

@tool
def search_gitlab_projects(query: str) -> List[Dict[str, Any]]:
    """
    Поиск репозиториев (проектов) в GitLab по строке запроса.
    Используйте для нахождения идентификатора проекта (project_id) по его названию.
    """
    gitlab_client = GitLabClient()
    projects = gitlab_client.search_projects(query)

    result = []
    for project in projects:
        result.append({
            "id": project.id,
            "name": project.name,
            "path_with_namespace": project.path_with_namespace,
            "description": project.description
        })
    return result

@tool
def get_gitlab_commits(project_id: str) -> List[Dict[str, Any]]:
    """
    Получение последних коммитов для проекта в GitLab по его ID.
    Используйте для анализа недавней активности в коде проекта.
    """
    gitlab_client = GitLabClient()
    commits = gitlab_client.get_project_commits(project_id)

    result = []
    for commit in commits[:20]: # Limit to 20 for context size
        result.append({
            "id": commit.id,
            "title": commit.title,
            "author_name": commit.author_name,
            "created_at": commit.created_at,
            "message": commit.message
        })
    return result

@tool
def query_gitlab_mrs(project_id: str, state: str = "opened") -> List[Dict[str, Any]]:
    """
    Получение списка Merge Requests (MR) для проекта в GitLab по его ID.
    Доступные статусы (state): 'opened', 'closed', 'merged', 'all'.
    Используйте для поиска активных или завершенных ревью кода.
    """
    gitlab_client = GitLabClient()
    mrs = gitlab_client.get_project_merge_requests(project_id, state=state)

    result = []
    for mr in mrs[:20]: # Limit to 20
        result.append({
            "id": mr.id,
            "iid": mr.iid,
            "title": mr.title,
            "state": mr.state,
            "author": mr.author.get("name", "") if hasattr(mr, "author") and isinstance(mr.author, dict) else getattr(mr.author, "name", "") if hasattr(mr, "author") else "",
            "source_branch": mr.source_branch,
            "target_branch": mr.target_branch
        })
    return result

@tool
def query_confluence(cql: str) -> List[Dict[str, Any]]:
    """
    Глобальный поиск по Confluence с использованием CQL (Confluence Query Language).
    Используйте для поиска страниц, пространств и документов по ключевым словам или метаданным.
    """
    confluence_client = ConfluenceClient()
    response = confluence_client.search_cql(cql)

    results = response.get("results", [])

    parsed_results = []
    for item in results[:10]: # Limit to 10
        content = item.get("content", {})
        parsed_results.append({
            "title": content.get("title", ""),
            "id": content.get("id", ""),
            "type": content.get("type", ""),
            "url": content.get("_links", {}).get("webui", ""),
            "excerpt": item.get("excerpt", "")
        })
    return parsed_results


@tool
def search_technical_docs(query: str) -> List[str]:
    """
    Семантический поиск по предварительно проиндексированным чанкам технической документации (Confluence) в OpenSearch.
    Используйте этот инструмент для получения детального технического контекста или выдержек из документации по конкретной теме.
    """
    openai_api_key = settings.get("OPENAI_API_KEY", "")
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)

    os_url = settings.get("OPENSEARCH_URL")
    os_user = settings.get("OPENSEARCH_USER")
    os_password = settings.get("OPENSEARCH_PASSWORD")
    verify_certs = settings.get("OPENSEARCH_VERIFY_CERTS", default=True)

    vectorstore = OpenSearchVectorSearch(
        opensearch_url=os_url,
        index_name="confluence-rag-index",
        embedding_function=embeddings,
        http_auth=(os_user, os_password),
        use_ssl=True,
        verify_certs=verify_certs,
        ssl_assert_hostname=verify_certs,
        ssl_show_warn=not verify_certs,
    )

    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    docs = retriever.invoke(query)

    return [doc.page_content for doc in docs]
