# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-44)
- [x] Initial setup, core sync, DB, agentic RAG workflows, Jira/GitLab maintenance.
- [x] Automations for code quality, Code Health, Analytics, Validation.
- [x] GitLab MR checks (Missing Tests, Missing Changelog, Title Linter, WIP Limit, Conflict Checker, etc.).
- [x] Jira and Confluence reminders and checks (Stale bugs, missing fields, resolutions, priority).
- [x] Jira Closed Missing Resolution Task to remind about missing resolutions.

### Phase 45: Jira Missing Due Date Reminder
- [x] Develop a task (`jira_missing_due_date_reminder_task`) to check Jira Epics that are in an "In Progress" state but lack a due date.
- [x] If no due date is set and no prior automated comment was left, leave an automated comment reminding the assignee or team to add a due date for better planning.
- [x] Register the task in the scheduler to run daily.
- [x] Add corresponding unit tests.
