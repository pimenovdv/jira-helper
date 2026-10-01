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
- [x] Phases 1-68: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, Confluence stale documentation archiver, Jira unassigned bug reminder, GitLab MR missing description reminder, Jira epic completion checker, Jira too many subtasks warning, Jira unassigned epic warning, GitLab MR secrets scanner, Confluence empty page checker, GitLab MR Too Many Commits Notifier, Jira Bug Missing Attachment Warning, Jira Stale Active Sprint Issue Warning, GitLab MR Missing Approvals Reminder, Jira Stale Backlog Task Reminder, GitLab MR Missing Changelog Label Checker, Jira Unestimated Bug Warning, and GitLab MR Stale Needs Work Reminder.


### Phase 69: GitLab MR Approved But Unmerged Reminder
- [x] Create `gitlab_mr_approved_but_unmerged_reminder_task` to check open MRs that are fully approved, have no merge conflicts, but haven't been merged after 3 days.
- [x] Post a comment reminding the author to merge the MR.

### Phase 70: Jira Stale Assigned Task Warning
- [ ] Create `jira_stale_assigned_task_warning_task` to check assigned tasks that haven't been transitioned or commented on for more than 7 days.
- [ ] Post a comment asking the assignee for a status update.
