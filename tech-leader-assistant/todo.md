# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-24)
- [x] Initial setup, UI dashboard, DB integrations (PostgreSQL, Neo4j, OpenSearch).
- [x] Jira/GitLab core sync logic and agentic RAG workflows (Slack, Confluence, Deep Research).
- [x] GitLab Automations: MR summarization, Code Review, Title Linter, missing labels, draft/merge cleanup, MR size labeler, pipeline failure notifications, empty description notifications, too many comments notifications, unresolved threads notifications, missing reviewer notifications, missing tests notifications.
- [x] Jira Automations: Weekly sprint summary, missing component/estimation/description/acceptance criteria reminders, overdue task reminders, unassigned sprint task reminders, stale task reminders, missing fixVersion reminders.
- [x] Phase 24: GitLab Long-Running MR Reminder, Jira Inactive Reporter Notification, Jira Blocked Task Alert

### Phase 25: New Automations and Features
