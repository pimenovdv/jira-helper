# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-47)
- [x] Initial setup, core sync, DB, agentic RAG workflows, Jira/GitLab maintenance.
- [x] Automations for code quality, Code Health, Analytics, Validation.
- [x] Assorted MR and Issue reminders, checkers, and summaries (stale approvals, due dates, branch deletion, WIP limits, etc).

### Phase 48: GitLab MR Missing Milestone Reminder
- [x] Develop a task (`gitlab_mr_missing_milestone_reminder_task`) to check open MRs in tracked GitLab projects.
- [x] Check if the MR lacks a milestone.
- [x] If so, leave an automated comment using ChatOpenAI reminding the author to add a milestone.
- [x] Register the task in the scheduler to run periodically.
- [x] Add corresponding unit tests.

### Phase 49: Jira Subtask Without Parent Warning
- [ ] Develop a task to check for subtasks that do not belong to a parent issue.
- [ ] Leave an automated comment warning the reporter.
