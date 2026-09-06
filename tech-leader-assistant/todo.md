# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-45)
- [x] Initial setup, core sync, DB, agentic RAG workflows, Jira/GitLab maintenance.
- [x] Automations for code quality, Code Health, Analytics, Validation.
- [x] GitLab MR checks (Missing Tests, Missing Changelog, Title Linter, WIP Limit, Conflict Checker, etc.).
- [x] Jira and Confluence reminders and checks (Stale bugs, missing fields, resolutions, priority, due date).
- [x] Jira Closed Missing Resolution Task to remind about missing resolutions.
- [x] Jira Missing Due Date Reminder to remind about missing due dates on Epics.

### Phase 46: GitLab MR Delete Source Branch Checker
- [x] Develop a task (`gitlab_mr_delete_source_branch_checker_task`) to check open MRs in tracked GitLab projects.
- [x] Verify if the source branch will be deleted upon merge.
- [x] If not, leave an automated comment asking the author to enable "Delete source branch when merge request is accepted".
- [x] Register the task in the scheduler to run periodically.
- [x] Add corresponding unit tests.
