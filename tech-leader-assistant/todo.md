# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-42)
- [x] Initial setup, core sync, DB, agentic RAG workflows, Jira/GitLab maintenance.
- [x] Automations for code quality, Code Health, Analytics, Validation.
- [x] GitLab MR checks (Missing Tests, Missing Changelog, Title Linter, WIP Limit, Conflict Checker, etc.).
- [x] Jira and Confluence reminders and checks.
- [x] Jira Stale Bug Escalation and GitLab MR Description Template Validator.

### Phase 43: Jira Missing Priority Reminder
- [x] Develop a task (`jira_missing_priority_reminder_task`) to check active Jira tasks that lack a priority assignment.
- [x] If no priority is set and no prior comment was left, leave an automated comment reminding the team to add one.
- [x] Register the task in the scheduler to run daily.
- [x] Add corresponding unit tests.
