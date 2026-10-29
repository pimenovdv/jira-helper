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
- [x] Phases 1-93: Initial setup, core sync, OpenSearch/Neo4j DBs, Confluence RAG workflows, and assorted Jira/GitLab/Confluence reminders, warnings, and code quality automations.

### Phase 94: Confluence Stale Page Warning
- [x] Create `confluence_stale_page_warning_task` to check for pages in Confluence that haven't been updated in over 1 year and leave a comment asking if the content is still relevant.
- [x] Schedule the task to run periodically in `app/scheduler.py`.
- [x] Add tests to verify the behavior.
