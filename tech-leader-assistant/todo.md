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
- [x] Phases 1-60: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, Confluence stale documentation archiver, Jira unassigned bug reminder, GitLab MR missing description reminder, Jira epic completion checker, Jira too many subtasks warning, Jira unassigned epic warning, GitLab MR secrets scanner, and Confluence empty page checker.

### Phase 61: GitLab MR Too Many Commits Notifier
- [x] Create `gitlab_mr_too_many_commits_notifier_task` to scan open MRs in GitLab.
- [x] If an MR has more than 20 commits, post a comment recommending the author to squash commits to keep the git history clean.
- [x] Include an HTML marker `<!-- AUTO_GENERATED_TOO_MANY_COMMITS_WARNING -->` to avoid duplicate comments.
