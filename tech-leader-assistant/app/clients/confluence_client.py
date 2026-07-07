from atlassian import Confluence
from .base import BaseClient
from . import settings

class ConfluenceClient(BaseClient):
    def __init__(self):
        self.url = settings.get("CONFLUENCE_URL")
        self.user = settings.get("CONFLUENCE_USER")
        self.token = settings.get("CONFLUENCE_TOKEN")
        self.client = Confluence(
            url=self.url,
            username=self.user,
            password=self.token
        )

    def ping(self) -> dict:
        try:
            # get_all_spaces checks if API is accessible
            self.client.get_all_spaces(start=0, limit=1)
            return {"status": "ok", "service": "Confluence", "url": self.url}
        except Exception as e:
            return {"status": "error", "service": "Confluence", "url": self.url, "error": str(e)}

    def search_cql(self, cql: str, limit: int = 10):
        try:
            return self.client.cql(cql, limit=limit)
        except Exception as e:
            return {}
