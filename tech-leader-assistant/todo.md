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
- [x] Phases 1-57: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, Confluence stale documentation archiver, Jira unassigned bug reminder, GitLab MR missing description reminder, Jira epic completion checker, and Jira too many subtasks warning.

### Phase 58: Jira Unassigned Epic Warning
- [x] Create `jira_unassigned_epic_warning_task` to identify Jira Epics that are unresolved and unassigned.
- [x] Add a comment suggesting the Epic needs an owner to drive its completion.
- [x] Include an auto-generated HTML marker `<!-- AUTO_GENERATED_UNASSIGNED_EPIC_WARNING -->`.
