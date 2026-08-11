# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-25)
- [x] Initial setup, UI dashboard, DB integrations. Jira/GitLab core sync logic and agentic RAG workflows.
- [x] GitLab & Jira Automations (Summarization, linting, cleanup, reminders, summaries).
- [x] Phase 24: GitLab Long-Running MR Reminder, Jira Inactive Reporter Notification, Jira Blocked Task Alert
- [x] Phase 25: GitLab MR Approval Reminder, Jira Missing Epic Link Reminder, Jira High Complexity Warning

### Phase 26: Code quality and workflow enforcement
- [x] GitLab Missing Assignee Notifier
- [x] Jira Missing Labels Reminder
- [x] GitLab Stale Draft MR Closer
