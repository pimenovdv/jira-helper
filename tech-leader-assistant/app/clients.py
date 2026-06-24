from dynaconf import Dynaconf

settings = Dynaconf(
    settings_files=["settings.toml"],
    environments=True,
    env_switcher="DYNACONF_ENV"
)

class GitLabDummyClient:
    def __init__(self):
        self.url = settings.get("GITLAB_URL")
        self.token = settings.get("GITLAB_TOKEN")

    def ping(self):
        return {"status": "ok", "service": "GitLab", "url": self.url}

class JiraDummyClient:
    def __init__(self):
        self.url = settings.get("JIRA_URL")

    def ping(self):
        return {"status": "ok", "service": "Jira", "url": self.url}

class ConfluenceDummyClient:
    def __init__(self):
        self.url = settings.get("CONFLUENCE_URL")

    def ping(self):
        return {"status": "ok", "service": "Confluence", "url": self.url}

class Neo4jDummyClient:
    def __init__(self):
        self.uri = settings.get("NEO4J_URI")

    def ping(self):
        return {"status": "ok", "service": "Neo4j", "uri": self.uri}

class OpenSearchDummyClient:
    def __init__(self):
        self.url = settings.get("OPENSEARCH_URL")

    def ping(self):
        return {"status": "ok", "service": "OpenSearch", "url": self.url}
