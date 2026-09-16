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
- [x] Phases 1-54: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, Confluence stale documentation archiver, and Jira unassigned bug reminder.

### Phase 55: GitLab MR Missing Description Reminder
- [x] Develop a task `gitlab_mr_missing_description_reminder_task` that identifies open GitLab Merge Requests lacking a meaningful description (e.g., empty or < 10 characters).
- [x] Automatically add a comment to these MRs reminding the author to provide a detailed description.
- [x] Include an auto-generated HTML marker `<!-- AUTO_GENERATED_MISSING_DESC_REMINDER -->` to avoid duplicate comments.

### Phase 56: Jira Epic Completion Checker
- [x] Create `jira_epic_completion_checker_task` to find Epics where all child issues are done, but the Epic itself is not marked as Done.
- [x] Add a comment to the Epic reminding the assignee or creator to close it.
- [x] Include an auto-generated HTML marker `<!-- AUTO_GENERATED_EPIC_COMPLETION_REMINDER -->`.
