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
- [x] Phases 1-74: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, and various warning tasks for missing attachments, unassigned/stale tasks, missing PR descriptions/approvals, unestimated bugs, missing MR reviewers/too short descriptions, and missing components warnings for Jira bugs.

### Phase 75: Jira Bug Missing Environment Warning
- [x] Create `jira_bug_missing_environment_warning_task` to check active Jira Bug issues to ensure they have the environment field populated.
- [x] If no environment is specified, post a comment asking the team to provide environment details for easier reproduction.

### Phase 76: Confluence Page Too Long Warning
- [x] Create `confluence_page_too_long_warning_task` to identify overly long Confluence pages and suggest splitting them.

### Phase 77: GitLab MR Reviewer Self-Assignment Checker
- [ ] Create `gitlab_mr_reviewer_self_assignment_warning_task` to advise against developers assigning themselves as the sole reviewer on their own Merge Requests.
