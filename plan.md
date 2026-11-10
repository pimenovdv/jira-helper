1. **Update `todo.md` (Compress & Plan Phase 109)**
   - Compress completed phases (1-108) into a concise summary using `replace_with_git_merge_diff`.
   - Add a new phase: "Phase 109: Jira Epic Missing Assignee Warning".
   - Define sub-tasks with empty checkboxes in `todo.md`.
   - Verify the `todo.md` changes using `cat`.
2. **Implement `jira_epic_missing_assignee_warning_task`**
   - Add a new async function `jira_epic_missing_assignee_warning_task` in `app/tasks.py` to fetch open Jira Epics without an assignee and add a warning comment with a specific HTML marker.
   - Verify the changes using `grep` and `cat`.
3. **Schedule the new task**
   - Modify `app/scheduler.py` to import and schedule `jira_epic_missing_assignee_warning_task` to run daily at 12:00.
   - Verify the schedule using `grep`.
4. **Add tests for Phase 109**
   - Create a new file `tests/test_jira_epic_missing_assignee_warning.py` with pytest covering the logic for missing assignees and duplicate comment prevention using mocks.
   - Verify the file contents using `cat`.
5. **Run test suite**
   - Run `uv run pytest --cov=app --cov-report=term-missing tests/` to ensure no regressions and verify the newly added test passes.
6. **Mark Phase 109 as completed in `todo.md`**
   - Modify `todo.md` to check off the newly completed tasks for Phase 109 using `replace_with_git_merge_diff`.
   - Verify the `todo.md` changes using `cat`.
7. **Complete pre-commit steps**
   - Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.
8. **Submit the changes**
   - Once all tests and pre-commit checks pass, I will submit the change with a descriptive commit message.
