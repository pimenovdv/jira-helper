from opensearchpy import OpenSearch
from .base import BaseClient
from . import settings

class OpenSearchClient(BaseClient):
    def __init__(self):
        self.url = settings.get("OPENSEARCH_URL")
        self.user = settings.get("OPENSEARCH_USER")
        self.password = settings.get("OPENSEARCH_PASSWORD")
        self.verify_certs = settings.get("OPENSEARCH_VERIFY_CERTS", default=True)
        self.client = OpenSearch(
            hosts=[self.url],
            http_compress=True,
            http_auth=(self.user, self.password),
            use_ssl=True,
            verify_certs=self.verify_certs,
            ssl_assert_hostname=self.verify_certs,
            ssl_show_warn=not self.verify_certs
        )

    def ping(self) -> dict:
        try:
            if self.client.ping():
                return {"status": "ok", "service": "OpenSearch", "url": self.url}
            else:
                return {"status": "error", "service": "OpenSearch", "url": self.url, "error": "Ping returned False"}
        except Exception as e:
            return {"status": "error", "service": "OpenSearch", "url": self.url, "error": str(e)}
