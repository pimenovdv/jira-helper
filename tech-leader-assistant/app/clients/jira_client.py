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
