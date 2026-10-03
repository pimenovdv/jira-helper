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
- [x] Phases 1-70: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, Confluence stale documentation archiver, Jira unassigned bug reminder, GitLab MR missing description reminder, Jira epic completion checker, Jira too many subtasks warning, Jira unassigned epic warning, GitLab MR secrets scanner, Confluence empty page checker, GitLab MR Too Many Commits Notifier, Jira Bug Missing Attachment Warning, Jira Stale Active Sprint Issue Warning, GitLab MR Missing Approvals Reminder, Jira Stale Backlog Task Reminder, GitLab MR Missing Changelog Label Checker, Jira Unestimated Bug Warning, GitLab MR Stale Needs Work Reminder, GitLab MR Approved But Unmerged Reminder, and Jira Stale Assigned Task Warning.


### Phase 71: Jira Unassigned In Progress Warning
- [x] Create `jira_unassigned_in_progress_warning_task` to check issues in "In Progress" status that have no assignee.
- [x] Post a comment asking to assign the issue to accurately track progress.
