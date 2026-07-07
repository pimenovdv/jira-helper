from dynaconf import Dynaconf

settings = Dynaconf(
    settings_files=["settings.toml"],
    environments=True,
    env_switcher="DYNACONF_ENV"
)

from .jira_client import JiraClient
from .gitlab_client import GitLabClient
from .confluence_client import ConfluenceClient
from .neo4j_client import Neo4jClient
from .opensearch_client import OpenSearchClient
