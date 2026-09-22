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
- [x] Phases 1-61: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, Confluence stale documentation archiver, Jira unassigned bug reminder, GitLab MR missing description reminder, Jira epic completion checker, Jira too many subtasks warning, Jira unassigned epic warning, GitLab MR secrets scanner, Confluence empty page checker, and GitLab MR Too Many Commits Notifier.

### Phase 62: Jira Bug Missing Attachment Warning
- [x] Create `jira_bug_missing_attachment_warning_task` to find unresolved Jira Bugs.
- [x] Check if the bug has any attachments (`issue.fields.attachment`).
- [x] If no attachments are found, post a comment advising the reporter to attach screenshots, logs, or other relevant files.
- [x] Include an HTML marker `<!-- AUTO_GENERATED_MISSING_ATTACHMENT_WARNING -->` to avoid duplicate comments.

### Phase 63: Jira Stale Active Sprint Issue Warning
- [ ] Create a task to find unresolved issues in active sprints that haven't had updates recently.
- [ ] If an issue is found, ping the assignee to provide an update or review the status.
