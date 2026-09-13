# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-52)
- [x] Initial setup, core sync, DB, agentic RAG workflows, Jira/GitLab maintenance.
- [x] Automations for code quality, Code Health, Analytics, Validation.
- [x] Assorted MR and Issue reminders, checkers, and summaries (stale approvals, due dates, branch deletion, WIP limits, missing milestones, subtask warnings, Confluence missing owner warning, GitLab stale thread reminder, missing release notes, etc).

### Phase 53: Confluence Stale Documentation Archiver
- [ ] Develop a task that identifies Confluence pages with the 'draft' or 'wip' label that haven't been updated in 6 months.
- [ ] Automatically add an 'archived' label and prefix the page title with '[ARCHIVED]'.
- [ ] Leave a comment tagging the last author explaining why it was archived.
