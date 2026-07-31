# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-17)
- [x] Initial setup (Clients, RAG Pipeline, Agentic Workflows).
- [x] GitLab Automations (Code Review, Stale Reminders, Size/Draft Labels, Branch Cleanup, Jira Validator, Conflict/Empty MR/CI Failure/Too Many Comments Notifiers).
- [x] Jira Automations (Missing Estimation/Acceptance Criteria/Overdue/Stale Task Reminders).

### Phase 18: Quality & Best Practices Automations
- [x] **GitLab MR Missing Tests Notifier**: Notify the author if an MR has significant code changes but no modifications to test files.
- [x] **Jira Task Missing Description Reminder**: Notify the assignee/reporter if a task lacks a meaningful description.
