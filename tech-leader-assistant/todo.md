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
- [x] Phases 1-56: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, Confluence stale documentation archiver, Jira unassigned bug reminder, GitLab MR missing description reminder, and Jira epic completion checker.

### Phase 57: Jira Too Many Subtasks Warning
- [x] Create `jira_too_many_subtasks_warning_task` to identify Jira issues (excluding Epics and Sub-tasks) that have 10 or more sub-tasks.
- [x] Add a comment suggesting the issue might be too large and could be converted into an Epic.
- [x] Include an auto-generated HTML marker `<!-- AUTO_GENERATED_TOO_MANY_SUBTASKS_WARNING -->`.
