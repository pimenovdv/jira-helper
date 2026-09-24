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
- [x] Phases 1-63: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, Confluence stale documentation archiver, Jira unassigned bug reminder, GitLab MR missing description reminder, Jira epic completion checker, Jira too many subtasks warning, Jira unassigned epic warning, GitLab MR secrets scanner, Confluence empty page checker, GitLab MR Too Many Commits Notifier, Jira Bug Missing Attachment Warning, and Jira Stale Active Sprint Issue Warning.

### Phase 64: GitLab MR Missing Approvals Reminder
- [x] Create `gitlab_mr_missing_approvals_reminder_task` to check open Merge Requests.
- [x] If an MR is older than a configured number of days (e.g., 3 days) and has not met the required number of approvals, ping the assigned reviewers or post a general comment.
- [x] Add an HTML marker `<!-- AUTO_GENERATED_MISSING_APPROVALS_REMINDER -->` to avoid duplicate comments.
