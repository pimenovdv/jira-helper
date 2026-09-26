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
- [x] Phases 1-64: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, Confluence stale documentation archiver, Jira unassigned bug reminder, GitLab MR missing description reminder, Jira epic completion checker, Jira too many subtasks warning, Jira unassigned epic warning, GitLab MR secrets scanner, Confluence empty page checker, GitLab MR Too Many Commits Notifier, Jira Bug Missing Attachment Warning, Jira Stale Active Sprint Issue Warning, and GitLab MR Missing Approvals Reminder.

### Phase 65: Jira Stale Backlog Task Reminder
- [x] Create `jira_stale_backlog_task_reminder_task` to check for issues in the 'Backlog' or 'To Do' state that have been untouched for more than 90 days.
- [x] Add a comment suggesting the team to refine, prioritize, or close the stale backlog issue.
- [x] Add an HTML marker `<!-- AUTO_GENERATED_STALE_BACKLOG_REMINDER -->` to avoid duplicate comments.

### Phase 66: GitLab MR Missing Changelog Label Checker
- [ ] Create `gitlab_mr_missing_changelog_label_checker_task` to check if an MR is missing a changelog-related label if the project enforces one.
- [ ] If the label is missing, add a comment indicating it should be added.
