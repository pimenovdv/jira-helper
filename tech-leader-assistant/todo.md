# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-37)
- [x] Initial setup, core sync (Jira/GitLab), DB, agentic RAG workflows, automated reminders.
- [x] Comprehensive automations for code quality, process enforcement, issue/PR maintenance, and GitLab MR missing description validation.
- [x] Code Health & Analytics (Code Churn Alerts, Stale Epic/MR Reminders, Confluence Author Summaries, Diagram Checkers).

### Phase 38: GitLab MR Missing Tests Checker
- [x] Develop a task (`gitlab_mr_missing_tests_checker_task`) to check open GitLab MRs for code changes without test changes.
- [x] If an MR modifies source files but no test files, add an automated comment asking the author to provide tests.
- [x] Register the task in the scheduler to run daily.
- [x] Add corresponding unit tests.
