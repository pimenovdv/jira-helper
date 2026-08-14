import pytest
from unittest.mock import MagicMock
from app.tasks import jira_high_priority_out_of_sprint_reminder_task

@pytest.mark.asyncio
async def test_jira_high_priority_out_of_sprint_reminder_no_api_key(mocker):
    # Mock settings to return empty API key
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, d="": "" if k == "OPENAI_API_KEY" else d
    mocker.patch("app.tasks.settings", mock_settings)

    result = await jira_high_priority_out_of_sprint_reminder_task()
    assert result == "Jira high priority out of sprint reminder task skipped (no OpenAI API key)"

@pytest.mark.asyncio
async def test_jira_high_priority_out_of_sprint_reminder_success(mocker):
    # Mock settings
    mock_settings = mocker.MagicMock()
    def settings_get(k, default=""):
        if k == "OPENAI_API_KEY":
            return "fake-key"
        if k == "JIRA_TRACKED_PROJECTS":
            return "PROJ"
        return default
    mock_settings.get.side_effect = settings_get
    mocker.patch("app.tasks.settings", mock_settings)

    # Mock JiraClient
    mock_jira = MagicMock()
    mocker.patch("app.tasks.JiraClient", return_value=mock_jira)

    # Mock LLM
    mock_llm = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = "Пожалуйста, возьмите задачу в спринт"
    mock_llm.ainvoke = mocker.AsyncMock(return_value=mock_resp)
    mocker.patch("app.tasks.ChatOpenAI", return_value=mock_llm)

    # Set up issues
    issue_no_remind = MagicMock()
    issue_no_remind.key = "PROJ-1"
    assignee = MagicMock()
    assignee.accountId = "123"
    issue_no_remind.fields.assignee = assignee

    issue_remind = MagicMock()
    issue_remind.key = "PROJ-2"
    issue_remind.fields.assignee = None

    mock_jira.search_issues.return_value = [issue_no_remind, issue_remind]

    # Set up comments
    comment1 = MagicMock()
    comment1.body = "<!-- AUTO_GENERATED_JIRA_HIGH_PRIORITY_OUT_OF_SPRINT_REMINDER -->"
    comment2 = MagicMock()
    comment2.body = "Random comment"

    def get_comments_side_effect(issue_key):
        if issue_key == "PROJ-1":
            return [comment1]
        return [comment2]

    mock_jira.get_comments.side_effect = get_comments_side_effect

    result = await jira_high_priority_out_of_sprint_reminder_task()

    assert result == "Jira high priority out of sprint reminder task completed."
    mock_jira.search_issues.assert_called_with('project = "PROJ" AND priority = Highest AND (sprint is EMPTY OR sprint not in openSprints()) AND statusCategory != Done')

    # Should only add comment to PROJ-2
    mock_jira.add_comment.assert_called_once()
    args, _ = mock_jira.add_comment.call_args
    assert args[0] == "PROJ-2"
    assert "<!-- AUTO_GENERATED_JIRA_HIGH_PRIORITY_OUT_OF_SPRINT_REMINDER -->\nПожалуйста, возьмите задачу в спринт" in args[1]

    mock_llm.ainvoke.assert_called_once()
    prompt_sent = mock_llm.ainvoke.call_args[0][0][1].content
    assert "Команда" in prompt_sent  # fallback assignee since none is set for PROJ-2

@pytest.mark.asyncio
async def test_jira_high_priority_out_of_sprint_reminder_exception(mocker):
    # Mock settings
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, d="": "fake-key" if k == "OPENAI_API_KEY" else ("PROJ" if k == "JIRA_TRACKED_PROJECTS" else d)
    mocker.patch("app.tasks.settings", mock_settings)

    # Mock JiraClient to throw Exception
    mock_jira = MagicMock()
    mock_jira.search_issues.side_effect = Exception("API Error")
    mocker.patch("app.tasks.JiraClient", return_value=mock_jira)
    mocker.patch("app.tasks.ChatOpenAI", return_value=MagicMock())

    result = await jira_high_priority_out_of_sprint_reminder_task()
    assert result == "Jira high priority out of sprint reminder task completed."
