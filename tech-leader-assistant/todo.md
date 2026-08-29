# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-38)
- [x] Initial setup, core sync, DB, agentic RAG workflows.
- [x] Automations for code quality, process enforcement, Jira/GitLab maintenance.
- [x] Code Health, Analytics, Reminders, Validation.
- [x] Missing Tests Checker for MRs.

### Phase 39: GitLab MR Missing Changelog Checker
- [x] Develop a task (`gitlab_mr_missing_changelog_checker_task`) to check open GitLab MRs for code changes without changelog updates.
- [x] If an MR modifies source files but no changelog files, add an automated comment asking the author to update the changelog.
- [x] Register the task in the scheduler to run daily.
- [x] Add corresponding unit tests.
