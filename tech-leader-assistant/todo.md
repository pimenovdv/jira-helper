# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-33)
- [x] Initial setup, core sync (Jira/GitLab), DB, agentic RAG workflows.
- [x] Comprehensive automations, workflow enforcements, metadata warnings, issue/PR maintenance, and Confluence sync.
- [x] Code Health & Analytics (Code Churn Alerts, Stale Epic Reminders, Confluence Author Summaries, Stale Page Reminders).
- [x] GitLab MR Missing Labels Notifier (Notifies authors if their open MR has no labels)
- [x] GitLab MR WIP Limit Reminder (Notifies authors with more than 3 open MRs about WIP limits).

### Phase 34: Jira Task Stale "In Progress" Reminder
- [x] Implement `jira_stale_in_progress_reminder_task` to query Jira for "In Progress" issues not updated for > 5 days.
- [x] Register task in scheduler.
- [x] Write unit tests for the reminder logic and test the marker mechanism.

### Phase 35: Confluence Page Stale Architecture Review Reminder
- [ ] Develop a task to check Confluence for architecture documents (by specific labels or spaces) that haven't been reviewed in 6 months.
- [ ] Post a comment tagging the document owner to initiate a review.
- [ ] Add tests for the Confluence reminder.
