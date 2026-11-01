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
- [x] Phases 1-98: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, various warning tasks for missing attachments, unassigned/stale tasks, missing PR descriptions/approvals, unestimated bugs, missing MR reviewers/too short descriptions, missing components/environment warnings for Jira bugs, confluence page length checks, MR reviewer self-assignment checks, GitLab MR missing milestone warning, Jira Epic Missing Due Date Warning, Jira Epic Without Child Issues Warning, Jira Story Missing Subtasks Warning, Jira Bug Missing Affected Version Warning, Jira Subtask Missing Estimate Warning, Jira Subtask Missing Assignee Warning, Jira Bug Missing Priority Warning, Confluence missing labels warning, GitLab stale WIP MR warning, Jira blocked issue follow-up reminder, Jira story missing description warning, GitLab MR missing labels warning, Jira epic missing description warning, Jira epic missing components warning, GitLab MR large diff warning, Jira subtask missing description warning, GitLab MR missing Jira key warning, Confluence missing last review date warning, GitLab MR missing target branch validator, and Jira epic missing priority warning.

### Phase 99: Confluence Outdated Architecture Diagram Warning
- [ ] Create `confluence_outdated_architecture_diagram_warning_task` in `app/tasks.py`. This task will query Confluence pages that contain architecture diagrams (e.g. searching for draw.io, gliffy, or specific image macros) and check their last updated date. If the diagram was added/updated over a year ago, it comments to remind the author to verify if the architecture diagram is still accurate.
- [ ] Schedule the task to run every week in `app/scheduler.py`.
- [ ] Add tests to verify behavior in `tests/test_confluence_outdated_architecture_diagram_warning.py`.
