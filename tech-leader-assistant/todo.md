# Tech Leader Assistant - TODO & Project Plan

## Core Features

1. **GitLab Sync & Timelines**
   - **Feature**: Scheduler to periodically extract data from GitLab based on config (projects & users).
   - **User Timeline**: Commits, active projects (projects with daily commits), MR approvals, branch creations, MR creations.
   - **Project Timeline**: Commits, active users, MR approvals, comments/reviews, branch/MR creation, merges.
   - **Real-time Visualization**: Stream these events to frontend timelines.

2. **Jira Sync & Issue Tracking**
   - **Feature**: Scheduler to pull Jira data.
   - **Sprint Tracking**: Active sprint tasks.
   - **Cross-Reference**: For each task (active or inactive sprint), display GitLab projects with branches matching the task ID.
   - **Releases**: List of releases, tasks included, and matching branches/projects.

3. **OpenSearch Integration & RAG Preparation**
   - **Feature**: Daily "gentle" extraction of data, chunking, and uploading to OpenSearch.
   - **Purpose**: Prepare data for Retrieval-Augmented Generation (RAG).

4. **Confluence Auto-Linking**
   - **Feature**: Automatically link Confluence pages to Git projects if page titles contain Git project names.
   - **Management**: Manual linking/unlinking capabilities.

5. **Confluence RAG**
   - **Feature**: Implement RAG capabilities to query Confluence documentation via LLM.

---

## Project Decomposition & Implementation Plan

### Phase 1-11: Completed Items
- [x] Architecture setup, Clients, RAG Pipeline, Agentic Workflows, Code Review, Stale Reminders, GitLab MR Automations (Size Labeler), etc.

### Phase 12: Repository Automations
- [x] **Automated Draft Labeler**: Implement `gitlab_draft_labeler_task` to check MR titles for "Draft:" or "WIP:" and automatically apply a `status: draft` label, or remove it if no longer present.
