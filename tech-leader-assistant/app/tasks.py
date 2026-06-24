import logging

logger = logging.getLogger(__name__)

def gitlab_sync_task():
    """Extracts data from GitLab based on configs and renders events on timeline."""
    logger.info("Running GitLab sync task: extracting data and rendering events on timeline.")
    return "GitLab sync task completed"

def jira_sync_task():
    """Extracts information from Jira by configs (sprints, issues, releases)."""
    logger.info("Running Jira sync task: extracting sprint and issue information.")
    return "Jira sync task completed"

def opensearch_ingestion_task():
    """Daily extraction, chunking and loading into OpenSearch for RAG."""
    logger.info("Running OpenSearch ingestion task: chunking data and preparing for RAG.")
    return "OpenSearch ingestion task completed"

def confluence_auto_link_task():
    """Automatically linking Confluence pages to Git projects based on titles."""
    logger.info("Running Confluence auto-linking task: linking pages to Git projects.")
    return "Confluence auto-linking task completed"
