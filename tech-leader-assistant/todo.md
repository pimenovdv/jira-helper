# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-21)
- [x] Setup, Agentic Workflows, GitLab/Jira Automations, Reminders, Reporting/Analytics, and MR Title Linter.

### Phase 22: Jira Automations - Missing Component Reminder
- [x] **Jira Missing Component Reminder Task**: Automatically check active Jira tasks to ensure they have an assigned component. Post a polite, LLM-generated reminder (in Russian) on tasks without components.
