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

    def get_user_events(self, user_id: str):
        try:
            user = self.client.users.get(user_id)
            # return user.events.list(all=True)
            return user.events.list(per_page=20)
        except Exception as e:
            return []

    def get_project_events(self, project_id: str):
        try:
            project = self.client.projects.get(project_id)
            # return project.events.list(all=True)
            return project.events.list(per_page=20)
        except Exception as e:
            return []

    def get_project_branches(self, project_id: str):
        try:
            project = self.client.projects.get(project_id)
            return project.branches.list(all=True)
        except Exception as e:
            return []
