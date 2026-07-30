# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Phases 1-16: Completed Items
- [x] Architecture setup, Clients, RAG Pipeline, Agentic Workflows, Code Review, Stale Reminders, GitLab MR Automations (Size Labeler, Draft Labeler, Merged Branch Cleanup, MR Jira Validator, MR Conflict Notifier, Empty MR Description Notifier), Jira Missing Estimation Reminder, GitLab Unresolved Threads Reminder.
- [x] GitLab MR CI/CD Failure Notifier.
- [x] Jira Task Missing Acceptance Criteria Reminder.

### Phase 17: Additional Automations
- [x] **GitLab MR Too Many Comments Notifier**: Notify the author or team if an MR has too many unresolved/resolved discussions (e.g., > 15), suggesting a synchronous meeting.
- [x] **Jira Overdue Task Reminder**: Check tasks in active sprints and comment if their due date is in the past.
