# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-35)
- [x] Initial setup, core sync (Jira/GitLab), DB, agentic RAG workflows.
- [x] Comprehensive automations, workflow enforcements, metadata warnings, issue/PR maintenance, and Confluence sync.
- [x] Code Health & Analytics (Code Churn Alerts, Stale Epic Reminders, Confluence Author Summaries, Stale Page Reminders, Stale Architecture Reminders).
- [x] GitLab MR Missing Labels Notifier (Notifies authors if their open MR has no labels)
- [x] GitLab MR WIP Limit Reminder (Notifies authors with more than 3 open MRs about WIP limits).
- [x] Jira Task Stale "In Progress" Reminder (Query Jira for "In Progress" issues not updated for > 5 days).

### Phase 36: Confluence Missing Diagram Checker
- [ ] Develop a task (`confluence_missing_diagram_checker_task`) to check Confluence architecture documents (pages with label 'architecture') for embedded diagrams (e.g. draw.io, plantuml, gliffy, mermaid macros or explicit image attachments).
- [ ] If an architecture document lacks diagrams, use the LLM to generate a comment suggesting the addition of a visual diagram for clarity.
- [ ] Register the task in the scheduler to run weekly.
- [ ] Add corresponding unit tests.
