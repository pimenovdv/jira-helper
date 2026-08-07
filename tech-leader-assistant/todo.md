# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-23)
- [x] Initial setup, UI dashboard, DB integrations (PostgreSQL, Neo4j, OpenSearch).
- [x] Jira/GitLab core sync logic and agentic RAG workflows (Slack, Confluence, Deep Research).
- [x] GitLab Automations: MR summarization, Code Review, Title Linter, missing labels, draft/merge cleanup, MR size labeler, pipeline failure notifications, empty description notifications, too many comments notifications, unresolved threads notifications, missing reviewer notifications, missing tests notifications.
- [x] Jira Automations: Weekly sprint summary, missing component/estimation/description/acceptance criteria reminders, overdue task reminders, unassigned sprint task reminders, stale task reminders, missing fixVersion reminders.

### Phase 24: New Automations and Features
- [x] **GitLab Long-Running MR Reminder**: Add a scheduled task to notify authors of MRs that have been open for an unusually long time (e.g., > 14 days), suggesting they be broken down or closed.
- [ ] **Jira Inactive Reporter Notification**: Add a task that tags the reporter of a Jira issue if the issue has been resolved for 3 days but hasn't been closed/verified by the reporter.
- [ ] **Jira Blocked Task Alert**: Add an automation that searches for tasks in an active sprint with a "Blocked" status for more than 2 days, and posts a comment tagging the Scrum Master or Tech Lead to help unblock it.
