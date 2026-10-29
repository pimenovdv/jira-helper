PLAYWRIGHT_BROWSERS_PATH=0 uv run playwright install chromium
PLAYWRIGHT_BROWSERS_PATH=0 uv run pytest --cov=app --cov-report=term-missing tests/
