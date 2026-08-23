# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-32)
- [x] Initial setup, core sync (Jira/GitLab), DB, agentic RAG workflows.
- [x] Comprehensive automations, workflow enforcements, metadata warnings, issue/PR maintenance, and Confluence sync.
- [x] Code Health & Analytics (Code Churn Alerts, Stale Epic Reminders, Confluence Author Summaries, Stale Page Reminders).
- [x] GitLab MR Missing Labels Notifier (Notifies authors if their open MR has no labels)

### Phase 33: GitLab MR WIP Limit Reminder Task
- [x] Implement task to track number of open MRs per author.
- [x] Notify authors with more than 3 open MRs about WIP (Work In Progress) limits.
