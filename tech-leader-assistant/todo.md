# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-39)
- [x] Initial setup, core sync, DB, agentic RAG workflows, Jira/GitLab maintenance.
- [x] Automations for code quality, Code Health, Analytics, Validation.
- [x] GitLab MR checks (Missing Tests, Missing Changelog, Title Linter, WIP Limit, etc.).
- [x] Jira and Confluence reminders and checks.

### Phase 40: Jira Stale Bug Escalation
- [x] Develop a task (`jira_stale_bug_escalation_task`) to check for "Bug" type issues open for more than 30 days.
- [x] If found, leave an automated comment escalating the bug and tag the reporter.
- [x] Register the task in the scheduler to run daily.
- [x] Add corresponding unit tests.

### Phase 41: GitLab MR Description Template Validator
- [x] Develop a task (`gitlab_mr_description_template_validator_task`) to check if open MRs contain required sections (e.g., `# How to test`).
- [x] If missing, leave an automated comment reminding the author to follow the template.
- [x] Register the task in the scheduler to run daily.
- [x] Add corresponding unit tests.
