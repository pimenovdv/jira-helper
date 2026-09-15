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
- [x] Phases 1-53: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, and Confluence stale documentation archiver.

### Phase 54: Jira Unassigned Bug Reminder
- [x] Develop a task `jira_unassigned_bug_reminder_task` that identifies Jira "Bug" issues that are unassigned, not done, and older than 2 days.
- [x] Automatically add a comment to these issues reminding the team to assign and triage them.
- [x] Include an auto-generated HTML marker to avoid duplicate comments.
