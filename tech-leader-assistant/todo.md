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
- [x] Phases 1-93: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, various warning tasks for missing attachments, unassigned/stale tasks, missing PR descriptions/approvals, unestimated bugs, missing MR reviewers/too short descriptions, missing components/environment warnings for Jira bugs, confluence page length checks, MR reviewer self-assignment checks, GitLab MR missing milestone warning, Jira Epic Missing Due Date Warning, Jira Epic Without Child Issues Warning, Jira Story Missing Subtasks Warning, Jira Bug Missing Affected Version Warning, Jira Subtask Missing Estimate Warning, Jira Subtask Missing Assignee Warning, Jira Bug Missing Priority Warning, Confluence missing labels warning, GitLab stale WIP MR warning, Jira blocked issue follow-up reminder, Jira story missing description warning, GitLab MR missing labels warning, Jira epic missing description warning, Jira epic missing components warning, and GitLab MR large diff warning.

### Phase 94: Confluence Stale Page Warning
- [x] Create `confluence_stale_page_warning_task` to check for pages in Confluence that haven't been updated in over 1 year and leave a comment asking if the content is still relevant.
- [x] Schedule the task to run periodically in `app/scheduler.py`.
- [x] Add tests to verify the behavior.

### Phase 95: Jira Task Missing Assignee Warning
- [ ] Create `jira_task_missing_assignee_warning_task` to warn in Jira if a task type issue has no assignee.
- [ ] Schedule the task to run periodically in `app/scheduler.py`.
- [ ] Add tests to verify the behavior.

### Phase 96: GitLab MR Description Missing Links Warning
- [ ] Create `gitlab_mr_missing_links_warning_task` to warn if MR description lacks HTTP links.
- [ ] Schedule the task to run periodically in `app/scheduler.py`.
- [ ] Add tests to verify the behavior.
