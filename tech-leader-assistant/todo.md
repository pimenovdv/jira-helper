# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-46)
- [x] Initial setup, core sync, DB, agentic RAG workflows, Jira/GitLab maintenance.
- [x] Automations for code quality, Code Health, Analytics, Validation.
- [x] GitLab MR checks (Missing Tests, Missing Changelog, Title Linter, WIP Limit, Conflict Checker, etc.).
- [x] Jira and Confluence reminders and checks (Stale bugs, missing fields, resolutions, priority, due date).
- [x] Jira Closed Missing Resolution Task to remind about missing resolutions.
- [x] Jira Missing Due Date Reminder to remind about missing due dates on Epics.
- [x] Phase 46: GitLab MR Delete Source Branch Checker (reminds authors to enable deleting source branch upon merge).

### Phase 47: GitLab MR Stale Approval Reminder
- [x] Develop a task (`gitlab_mr_stale_approval_reminder_task`) to check open MRs in tracked GitLab projects.
- [x] Check if the MR has approvals but hasn't been updated for > 3 days.
- [x] If so, leave an automated comment using ChatOpenAI reminding the reviewers or author to merge.
- [x] Register the task in the scheduler to run periodically.
- [x] Add corresponding unit tests.
