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

    def link_task_to_project(self, task_id: str, project_id: str):
        query = """
        MERGE (t:Task {id: $task_id})
        MERGE (p:Project {id: $project_id})
        MERGE (t)-[:BELONGS_TO]->(p)
        """
        try:
            with self.driver.session() as session:
                session.run(query, task_id=task_id, project_id=project_id)
        except Exception:
            pass

    def link_release_to_project(self, release_name: str, project_id: str):
        query = """
        MERGE (r:Release {name: $release_name})
        MERGE (p:Project {id: $project_id})
        MERGE (r)-[:BELONGS_TO]->(p)
        """
        try:
            with self.driver.session() as session:
                session.run(query, release_name=release_name, project_id=project_id)
        except Exception:
            pass

    def cleanup_ghost_nodes(self, active_tasks: list, active_releases: list, active_projects: list):
        # We find and delete Task, Release, Project nodes that are not in the given active lists
        try:
            with self.driver.session() as session:
                if active_tasks:
                    session.run("MATCH (t:Task) WHERE NOT t.id IN $active_tasks DETACH DELETE t", active_tasks=active_tasks)
                if active_releases:
                    session.run("MATCH (r:Release) WHERE NOT r.name IN $active_releases DETACH DELETE r", active_releases=active_releases)
                if active_projects:
                    session.run("MATCH (p:Project) WHERE NOT p.id IN $active_projects DETACH DELETE p", active_projects=active_projects)
        except Exception:
            pass

    def __del__(self):
        if hasattr(self, 'driver'):
            self.driver.close()
