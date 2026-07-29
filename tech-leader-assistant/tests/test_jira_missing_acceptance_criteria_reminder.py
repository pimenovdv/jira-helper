import pytest
from unittest.mock import MagicMock

from app.tasks import jira_missing_acceptance_criteria_reminder_task

@pytest.mark.asyncio
async def test_jira_missing_ac_skip_no_api_key(mocker):
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda k, d="": "" if k == "OPENAI_API_KEY" else d
    mocker.patch("app.tasks.settings", mock_settings)

    result = await jira_missing_acceptance_criteria_reminder_task()
    assert "skipped (no OpenAI API key)" in result

@pytest.mark.asyncio
async def test_jira_missing_ac_reminder_task(mocker):
    mock_settings = MagicMock()
    def settings_get(key, default=""):
        if key == "OPENAI_API_KEY":
            return "fake-key"
        if key == "JIRA_TRACKED_PROJECTS":
            return "PROJ"
        return default
    mock_settings.get.side_effect = settings_get
    mocker.patch("app.tasks.settings", mock_settings)

    # Mock ChatOpenAI
    mock_llm_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Please add AC! <!-- AUTO_GENERATED_JIRA_MISSING_AC_REMINDER -->"
    mock_llm_instance.invoke.return_value = mock_response
    mocker.patch("app.tasks.ChatOpenAI", return_value=mock_llm_instance)

    # Mock Jira Client
    mock_jira_client_class = MagicMock()
    mock_jira_instance = MagicMock()
    mock_jira_client_class.return_value = mock_jira_instance
    mocker.patch("app.tasks.JiraClient", mock_jira_client_class)

    # Task 1: Has AC in English
    issue1 = MagicMock()
    issue1.key = "PROJ-1"
    issue1.fields.description = "Some description with Acceptance Criteria"

    # Task 2: Has AC in Russian
    issue2 = MagicMock()
    issue2.key = "PROJ-2"
    issue2.fields.description = "Критерии приемки: все работает"

    # Task 3: Missing AC, already notified
    issue3 = MagicMock()
    issue3.key = "PROJ-3"
    issue3.fields.description = "Just a task."
    issue3.fields.summary = "Summary 3"
    comment3 = MagicMock()
    comment3.body = "Hey <!-- AUTO_GENERATED_JIRA_MISSING_AC_REMINDER -->"

    # Task 4: Missing AC, not notified
    issue4 = MagicMock()
    issue4.key = "PROJ-4"
    issue4.fields.description = "Just another task."
    issue4.fields.summary = "Summary 4"

    # Task 5: Empty description
    issue5 = MagicMock()
    issue5.key = "PROJ-5"
    issue5.fields.description = None
    issue5.fields.summary = "Summary 5"

    mock_jira_instance.search_issues.return_value = [issue1, issue2, issue3, issue4, issue5]

    def mock_get_comments(key):
        if key == "PROJ-3":
            return [comment3]
        return []
    mock_jira_instance.get_comments.side_effect = mock_get_comments

    result = await jira_missing_acceptance_criteria_reminder_task()
    assert result == "Jira missing acceptance criteria reminder task completed"

    # LLM should be invoked twice (for PROJ-4 and PROJ-5)
    assert mock_llm_instance.invoke.call_count == 2

    # Add comment should be called twice (for PROJ-4 and PROJ-5)
    assert mock_jira_instance.add_comment.call_count == 2
    mock_jira_instance.add_comment.assert_any_call("PROJ-4", mock_response.content)
    mock_jira_instance.add_comment.assert_any_call("PROJ-5", mock_response.content)
