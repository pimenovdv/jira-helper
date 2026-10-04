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
- [x] Phases 1-71: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, and various warning tasks for missing attachments, unassigned/stale tasks, missing PR descriptions/approvals, and unestimated bugs.

### Phase 72: GitLab MR Missing Reviewers Notifier
- [x] Create `gitlab_mr_missing_reviewers_notifier_task` to check open MRs that do not have reviewers assigned.
- [x] Post a comment asking the author to add reviewers to the MR to proceed with code review.
