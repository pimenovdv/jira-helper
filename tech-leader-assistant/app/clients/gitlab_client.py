import gitlab
from .base import BaseClient
from . import settings

class GitLabClient(BaseClient):
    def __init__(self):
        self.url = settings.get("GITLAB_URL")
        self.token = settings.get("GITLAB_TOKEN")
        self.client = gitlab.Gitlab(url=self.url, private_token=self.token)

    def ping(self) -> dict:
        try:
            self.client.auth()
            return {"status": "ok", "service": "GitLab", "url": self.url}
        except Exception as e:
            return {"status": "error", "service": "GitLab", "url": self.url, "error": str(e)}
