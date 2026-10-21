# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases
- [x] Phases 1-84: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, various warning tasks for missing attachments, unassigned/stale tasks, missing PR descriptions/approvals, unestimated bugs, missing MR reviewers/too short descriptions, missing components/environment warnings for Jira bugs, confluence page length checks, MR reviewer self-assignment checks, GitLab MR missing milestone warning, Jira Epic Missing Due Date Warning, Jira Epic Without Child Issues Warning, Jira Story Missing Subtasks Warning, Jira Bug Missing Affected Version Warning, Jira Subtask Missing Estimate Warning, and Jira Subtask Missing Assignee Warning.

### Phase 85: Jira Bug Missing Priority Warning
- [x] Create `jira_bug_missing_priority_warning_task` to iterate through open bugs in Jira and warn if they are missing a priority.
- [x] Schedule the task to run periodically in `app/scheduler.py`.
- [x] Add tests in `tests/test_jira_bug_missing_priority_warning.py` to verify the behavior.
