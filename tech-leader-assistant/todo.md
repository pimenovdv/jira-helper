# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-29)
- [x] Initial setup, UI dashboard, DB integrations. Jira/GitLab core sync logic and agentic RAG workflows.
- [x] GitLab & Jira Automations (Summarization, linting, cleanup, reminders, summaries).
- [x] Workflow enforcements, code quality notifications, stalled/blocked task reminders, missing assignments, metadata warnings and backlog tracking health.
- [x] Issue & PR Maintenance (Decomposition, out-of-sprint warnings, description checklists).
- [x] Confluence & Knowledge Sync Integrations (Confluence tags, Neo4j ghost cleanup, OpenSearch expiration).

### Phase 30: Analytics & Code Health
- [x] GitLab Code Churn Alert (Alerts when an MR introduces significant code churn > 1000 lines)
- [x] Jira Stale Epic Reminder (Notifies if an Epic hasn't seen updates for a long time)
- [ ] Confluence Author Summary (Generates periodic summary of recently contributed pages by author)
