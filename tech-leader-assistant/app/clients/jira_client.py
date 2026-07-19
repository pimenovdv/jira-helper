from jira import JIRA
from .base import BaseClient
from . import settings

class JiraClient(BaseClient):
    def __init__(self):
        self.url = settings.get("JIRA_URL")
        self.user = settings.get("JIRA_USER")
        self.token = settings.get("JIRA_TOKEN")
        self.client = JIRA(server=self.url, basic_auth=(self.user, self.token))

    def ping(self) -> dict:
        try:
            # myself() throws an exception if authentication fails
            self.client.myself()
            return {"status": "ok", "service": "Jira", "url": self.url}
        except Exception as e:
            return {"status": "error", "service": "Jira", "url": self.url, "error": str(e)}

    def get_project_versions(self, project_key: str):
        try:
            return self.client.project_versions(project_key)
        except Exception as e:
            return []

    def search_issues(self, jql: str):
        try:
            return self.client.search_issues(jql, maxResults=100)
        except Exception as e:
            return []

    def get_comments(self, issue_key: str):
        try:
            return self.client.comments(issue_key)
        except Exception as e:
            return []

    def add_comment(self, issue_key: str, body: str):
        try:
            return self.client.add_comment(issue_key, body)
        except Exception as e:
            return None
