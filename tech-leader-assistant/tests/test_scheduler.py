import pytest
import asyncio
from app.scheduler import start_scheduler, shutdown_scheduler, scheduler

@pytest.mark.asyncio
async def test_scheduler_lifecycle():
    # Ensure it's not running initially
    assert not scheduler.running

    # Start it
    start_scheduler()
    assert scheduler.running

    # Check if jobs were added
    jobs = scheduler.get_jobs()
    job_ids = [job.id for job in jobs]
    assert "gitlab_sync" in job_ids
    assert "jira_sync" in job_ids
    assert "opensearch_ingestion" in job_ids
    assert "confluence_auto_link" in job_ids

    # Shutdown it
    shutdown_scheduler()

    # Let the event loop execute the scheduled shutdown callback
    await asyncio.sleep(0.1)

    assert not scheduler.running
