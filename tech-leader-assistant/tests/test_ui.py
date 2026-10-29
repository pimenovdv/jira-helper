import pytest
from playwright.async_api import async_playwright
import uvicorn
import asyncio
from app.main import app
import multiprocessing
import time
import requests
from contextlib import asynccontextmanager

@asynccontextmanager
async def dummy_lifespan(app):
    yield

def run_server():
    # Replace lifespan to avoid DB connection errors during test
    app.router.lifespan_context = dummy_lifespan
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="error")

@pytest.fixture(scope="module", autouse=True)
def test_server():
    process = multiprocessing.Process(target=run_server)
    process.start()

    # Wait for server to start
    for _ in range(30):
        try:
            requests.get("http://127.0.0.1:8001/api/health")
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.1)
    else:
        process.terminate()
        process.join()
        pytest.fail("Server did not start in time")

    yield

    process.terminate()
    process.join()

@pytest.mark.asyncio
async def test_dashboard_renders():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # intercept the API call to return a known mock response
        await page.route("**/api/health", lambda route: route.fulfill(
            json={
                "status": "active",
                "clients": [
                    {"service": "Mock Gitlab", "status": "ok", "url": "http://mock-gitlab"}
                ]
            }
        ))

        await page.goto("http://127.0.0.1:8001/")

        # Wait for vue to render the mock data
        await page.wait_for_selector("text=Mock Gitlab")

        # Check if the title is present
        title = await page.title()
        assert title == "Tech Leader Assistant Dashboard"

        # Check if the mock data is displayed correctly
        content = await page.content()
        assert "Mock Gitlab" in content
        assert "http://mock-gitlab" in content

        await browser.close()

@pytest.mark.asyncio
async def test_timeline_renders():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # intercept the health API call to return a known mock response to avoid health check errors
        await page.route("**/api/health", lambda route: route.fulfill(
            json={
                "status": "active",
                "clients": []
            }
        ))

        # intercept the timeline API call to return mock events
        await page.route("**/api/timeline/user/user123", lambda route: route.fulfill(
            json={
                "user_id": "user123",
                "events": [
                    {
                        "id": 1,
                        "type": "commit",
                        "timestamp": "2023-10-27T10:00:00Z",
                        "data": {"message": "Initial commit"}
                    }
                ]
            }
        ))

        await page.goto("http://127.0.0.1:8001/")

        # Interact with the UI
        await page.select_option('select', 'user')
        await page.fill('input[placeholder="Enter ID"]', 'user123')
        await page.click('button:has-text("Load Timeline")')

        # Wait for the vis-timeline item to render
        await page.wait_for_selector(".vis-item-content")

        # Verify the content
        content = await page.text_content(".vis-item-content")
        assert "commit" in content

        await browser.close()

@pytest.mark.asyncio
async def test_dashboard_tasks_renders():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # intercept the health API call to avoid errors
        await page.route("**/api/health", lambda route: route.fulfill(
            json={
                "status": "active",
                "clients": []
            }
        ))

        # intercept the tasks API call
        await page.route("**/api/dashboard/tasks", lambda route: route.fulfill(
            json={
                "tasks": [
                    {
                        "task_id": "TEST-123",
                        "summary": "Mock UI Task",
                        "fix_versions": ["1.0", "1.1"],
                        "matched_gitlab_projects": ["ui-project"],
                        "timestamp": "2023-11-01T10:00:00Z"
                    }
                ]
            }
        ))

        await page.goto("http://127.0.0.1:8001/")

        # Click the Load Tasks button
        await page.click('button:has-text("Load Tasks")')

        # Wait for the task table to render the task
        await page.wait_for_selector("text=TEST-123")

        # Verify the contents
        content = await page.content()
        assert "TEST-123" in content
        assert "Mock UI Task" in content
        assert "1.0, 1.1" in content
        assert "ui-project" in content

        await browser.close()

@pytest.mark.asyncio
async def test_chat_interface_renders_and_functions():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # intercept the health API call to avoid errors
        await page.route("**/api/health", lambda route: route.fulfill(
            json={
                "status": "active",
                "clients": []
            }
        ))

        # intercept the chat API call
        await page.route("**/api/chat", lambda route: route.fulfill(
            json={
                "question": "What is the project structure?",
                "answer": "This is a mock assistant response.",
                "documents": ["Mock source document 1", "Mock source document 2"]
            }
        ))

        await page.goto("http://127.0.0.1:8001/")

        # Wait for the Chat input to appear
        await page.wait_for_selector('input[placeholder="Type your message..."]')

        # Fill the chat input and click send
        await page.fill('input[placeholder="Type your message..."]', "What is the project structure?")
        await page.click('button:has-text("Send")')

        # Wait for the mock response to appear
        await page.wait_for_selector("text=This is a mock assistant response.")

        # Verify the contents
        content = await page.content()
        assert "What is the project structure?" in content
        assert "This is a mock assistant response." in content
        assert "Mock source document 1" in content
        assert "Mock source document 2" in content

        await browser.close()
