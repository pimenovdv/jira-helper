# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-26)
- [x] Initial setup, UI dashboard, DB integrations. Jira/GitLab core sync logic and agentic RAG workflows.
- [x] GitLab & Jira Automations (Summarization, linting, cleanup, reminders, summaries).
- [x] Phases 24-26: Workflow enforcements, code quality notifications, stalled/blocked task reminders, missing assignments and metadata warnings.

### Phase 27: Backlog and tracking health
- [x] GitLab Missing Milestone Notifier
