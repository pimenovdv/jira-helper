# Tech Leader Assistant - TODO & Project Plan

## Core Features
1. **GitLab Sync & Timelines**: Scheduler to periodically extract data from GitLab based on config (projects & users). Real-time Visualization.
2. **Jira Sync & Issue Tracking**: Scheduler to pull Jira data. Sprint Tracking, Cross-Reference with GitLab, Releases.
3. **OpenSearch Integration**: Data extraction, chunking, and uploading to OpenSearch for RAG.
4. **Confluence Auto-Linking**: Automatically link Confluence pages to Git projects.
5. **Confluence RAG**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Completed Phases (1-20)
- [x] Setup, Agentic Workflows, GitLab/Jira Automations, Reminders, and Reporting/Analytics.

### Phase 21: GitLab Automations - MR Title Linter
- [x] **GitLab MR Title Linter Task**: Automatically check GitLab Merge Request titles and enforce standard naming conventions. Post a polite, LLM-generated reminder (in Russian) if the title does not meet the standards (e.g., missing Conventional Commits prefix or Jira ticket ID).
