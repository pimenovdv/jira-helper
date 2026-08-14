import pytest
from unittest.mock import MagicMock
from app.tasks import gitlab_mr_description_checklist_validator_task

@pytest.mark.asyncio
async def test_gitlab_mr_description_checklist_validator_no_api_key(mocker):
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, d="": "" if k == "OPENAI_API_KEY" else d
    mocker.patch("app.tasks.settings", mock_settings)

    result = await gitlab_mr_description_checklist_validator_task()
    assert result == "GitLab MR description checklist validator task skipped (no OpenAI API key)"

@pytest.mark.asyncio
async def test_gitlab_mr_description_checklist_validator_success(mocker):
    # Mock settings
    mock_settings = mocker.MagicMock()
    def settings_get(k, default=""):
        if k == "OPENAI_API_KEY":
            return "fake-key"
        if k == "GITLAB_TRACKED_PROJECTS":
            return "GL-1"
        return default
    mock_settings.get.side_effect = settings_get
    mocker.patch("app.tasks.settings", mock_settings)

    # Mock GitLabClient
    mock_gl = MagicMock()
    mocker.patch("app.tasks.GitLabClient", return_value=mock_gl)

    # Mock LLM
    mock_llm = MagicMock()
    mock_resp = MagicMock()
    mock_resp.content = "Добавьте чек-лист"
    mock_llm.ainvoke = mocker.AsyncMock(return_value=mock_resp)
    mocker.patch("app.tasks.ChatOpenAI", return_value=mock_llm)

    # Setup MRs
    mr1 = {"iid": 1, "description": "some desc without checklist", "author": {"username": "testuser"}}
    mr2 = {"iid": 2, "description": "has checklist [ ]", "author": {"username": "user2"}}
    mr3 = {"iid": 3, "description": "already reminded", "author": {"username": "user3"}}

    mock_gl.get_project_mrs.return_value = [mr1, mr2, mr3]

    # Setup Notes
    note1 = MagicMock()
    note1.body = "just a comment"

    note3 = MagicMock()
    note3.body = "<!-- AUTO_GENERATED_GITLAB_MR_CHECKLIST_VALIDATOR -->\nДобавьте чек-лист"

    def get_mr_notes_side_effect(proj, iid):
        if iid == 1:
            return [note1]
        elif iid == 3:
            return [note3]
        return []

    mock_gl.get_mr_notes.side_effect = get_mr_notes_side_effect

    result = await gitlab_mr_description_checklist_validator_task()
    assert result == "GitLab MR description checklist validator task completed."

    # Should only create note for mr1
    mock_gl.create_mr_note.assert_called_once()
    args, _ = mock_gl.create_mr_note.call_args
    assert args[0] == "GL-1"
    assert args[1] == 1
    assert "<!-- AUTO_GENERATED_GITLAB_MR_CHECKLIST_VALIDATOR -->\nДобавьте чек-лист" in args[2]

    mock_llm.ainvoke.assert_called_once()
    prompt_sent = mock_llm.ainvoke.call_args[0][0][1].content
    assert "@testuser" in prompt_sent

@pytest.mark.asyncio
async def test_gitlab_mr_description_checklist_validator_exception(mocker):
    # Mock settings
    mock_settings = mocker.MagicMock()
    mock_settings.get.side_effect = lambda k, d="": "fake-key" if k == "OPENAI_API_KEY" else ("GL-1" if k == "GITLAB_TRACKED_PROJECTS" else d)
    mocker.patch("app.tasks.settings", mock_settings)

    # Mock GitLabClient to throw Exception
    mock_gl = MagicMock()
    mock_gl.get_project_mrs.side_effect = Exception("API Error")
    mocker.patch("app.tasks.GitLabClient", return_value=mock_gl)
    mocker.patch("app.tasks.ChatOpenAI", return_value=MagicMock())

    result = await gitlab_mr_description_checklist_validator_task()
    assert result == "GitLab MR description checklist validator task completed."
