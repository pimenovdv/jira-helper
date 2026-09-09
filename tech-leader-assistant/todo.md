# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-49)
- [x] Initial setup, core sync, DB, agentic RAG workflows, Jira/GitLab maintenance.
- [x] Automations for code quality, Code Health, Analytics, Validation.
- [x] Assorted MR and Issue reminders, checkers, and summaries (stale approvals, due dates, branch deletion, WIP limits, missing milestones, subtask warnings, etc).

### Phase 50: Confluence Missing Owner Warning
- [ ] Develop a task to check Confluence pages for missing owner tags.
- [ ] Notify the creator to add an owner tag.
