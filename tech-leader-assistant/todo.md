# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-36)
- [x] Initial setup, core sync (Jira/GitLab), DB, agentic RAG workflows, automated reminders.
- [x] Comprehensive automations for code quality, process enforcement, and issue/PR maintenance.
- [x] Code Health & Analytics (Code Churn Alerts, Stale Epic/MR Reminders, Confluence Author Summaries, Diagram Checkers).
- [x] Confluence Missing Diagram Checker

### Phase 37: GitLab MR Missing Description Validation
- [x] Develop a task (`gitlab_mr_missing_description_notifier_task`) to check open GitLab MRs and ensure they have a non-empty description.
- [x] If an MR lacks a description, add an automated comment asking the author to provide one, explaining the context of the changes.
- [x] Register the task in the scheduler to run daily.
- [x] Add corresponding unit tests.
