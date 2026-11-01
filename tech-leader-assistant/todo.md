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
- [x] Phases 1-96: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, various warning tasks for missing attachments, unassigned/stale tasks, missing PR descriptions/approvals, unestimated bugs, missing MR reviewers/too short descriptions, missing components/environment warnings for Jira bugs, confluence page length checks, MR reviewer self-assignment checks, GitLab MR missing milestone warning, Jira Epic Missing Due Date Warning, Jira Epic Without Child Issues Warning, Jira Story Missing Subtasks Warning, Jira Bug Missing Affected Version Warning, Jira Subtask Missing Estimate Warning, Jira Subtask Missing Assignee Warning, Jira Bug Missing Priority Warning, Confluence missing labels warning, GitLab stale WIP MR warning, Jira blocked issue follow-up reminder, Jira story missing description warning, GitLab MR missing labels warning, Jira epic missing description warning, Jira epic missing components warning, GitLab MR large diff warning, Jira subtask missing description warning, GitLab MR missing Jira key warning, and Confluence missing last review date warning.

### Phase 97: GitLab MR Missing Target Branch Validator
- [ ] Create `gitlab_mr_missing_target_branch_validator_task` in `app/tasks.py`. This task checks active MRs to ensure their target branch matches standard repository guidelines (e.g. not merging directly into `main` without proper labels/configuration, or reminding developers to merge to an integration branch first). If merging into `main` without specific label, add warning comment.
- [ ] Schedule the task to run periodically in `app/scheduler.py`.
- [ ] Add tests to verify behavior in `tests/test_gitlab_mr_missing_target_branch_validator.py`.
