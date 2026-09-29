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
- [x] Phases 1-66: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, Confluence stale documentation archiver, Jira unassigned bug reminder, GitLab MR missing description reminder, Jira epic completion checker, Jira too many subtasks warning, Jira unassigned epic warning, GitLab MR secrets scanner, Confluence empty page checker, GitLab MR Too Many Commits Notifier, Jira Bug Missing Attachment Warning, Jira Stale Active Sprint Issue Warning, GitLab MR Missing Approvals Reminder, Jira Stale Backlog Task Reminder, and GitLab MR Missing Changelog Label Checker.


### Phase 67: Jira Unestimated Bug Warning
- [x] Create `jira_unestimated_bug_warning_task` to check if a Bug in an active sprint lacks a time tracking original estimate or story points.
- [x] Post a comment warning that it should be estimated to track capacity accurately.

### Phase 68: GitLab MR Stale Needs Work Reminder
- [x] Create `gitlab_mr_stale_needs_work_reminder_task` to check open MRs that have a 'needs work' or 'changes requested' label but no recent commits.
- [x] Post a comment reminding the author to address the feedback.
