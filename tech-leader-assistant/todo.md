# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-18)
- [x] Initial setup (Clients, RAG Pipeline, Agentic Workflows).
- [x] GitLab Automations (Code Review, Stale Reminders, Size/Draft Labels, Branch Cleanup, Jira Validator, Conflict/Empty MR/CI Failure/Too Many Comments/Missing Tests Notifiers).
- [x] Jira Automations (Missing Estimation/Acceptance Criteria/Overdue/Stale Task/Missing Description Reminders).

### Completed Phases (19)
- [x] Workflow & Assignment Automations (GitLab MR Missing Reviewer Notifier, Jira Sprint Unassigned Task Reminder).

### Phase 20: Reporting & Analytics
- [ ] **Weekly Sprint Summary Generation**: Automatically generate and post a summary of the current sprint's progress (completed vs pending tasks) to a designated Confluence page.
