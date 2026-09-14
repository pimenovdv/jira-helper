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
- [x] Phases 1-52: Initial setup, core sync, DB, RAG workflows, code quality automations, and assorted Jira/GitLab/Confluence reminders and checks.

### Phase 53: Confluence Stale Documentation Archiver
- [x] Develop a task that identifies Confluence pages with the 'draft' or 'wip' label that haven't been updated in 6 months.
- [x] Automatically add an 'archived' label and prefix the page title with '[ARCHIVED]'.
- [x] Leave a comment tagging the last author explaining why it was archived.
