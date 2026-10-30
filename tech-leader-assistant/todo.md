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

### Phase 94: GitLab MR Missing Jira Link Warning
- [x] Create `gitlab_mr_missing_jira_link_warning_task` to check open Merge Requests in GitLab to warn if the MR title or description is missing a Jira issue key.
- [x] Schedule the task to run periodically in `app/scheduler.py`.
- [x] Add tests to verify the behavior.

### Phase 95: Jira Story Missing Story Points Warning
- [ ] Create `jira_story_missing_story_points_warning_task` to check open Stories in Jira to warn if the Story is missing story points.
- [ ] Schedule the task to run periodically in `app/scheduler.py`.
- [ ] Add tests to verify the behavior.
