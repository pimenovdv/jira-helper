from neo4j import GraphDatabase
from .base import BaseClient
from . import settings

class Neo4jClient(BaseClient):
    def __init__(self):
        self.uri = settings.get("NEO4J_URI")
        self.user = settings.get("NEO4J_USER")
        self.password = settings.get("NEO4J_PASSWORD")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def ping(self) -> dict:
        try:
            self.driver.verify_connectivity()
            return {"status": "ok", "service": "Neo4j", "uri": self.uri}
        except Exception as e:
            return {"status": "error", "service": "Neo4j", "uri": self.uri, "error": str(e)}

    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.close()
