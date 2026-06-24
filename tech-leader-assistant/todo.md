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

### Phase 1: Foundation & Skeleton (Current Phase)
- [x] Initialize python project with `uv` (FastAPI, dynaconf, OpenAI, langgraph, gitlab, jira, atlassian, neo4j, opensearch).
- [x] Create project structure and guidelines (`AGENTS.md`).
- [x] Create `Dockerfile` and `docker-compose.yml`.
- [x] Implement simple FastAPI backend for basic health checks and dummy client connections.
- [x] Implement simple HTML+JS frontend to visualize system statuses.

### Phase 2: Data Ingestion & Clients
- [x] Implement genuine `GitLabClient` with token authentication.
- [x] Implement genuine `JiraClient` and `ConfluenceClient`.
- [x] Implement `Neo4jClient` for graphing relationships (Task -> Branch -> Project).
- [x] Implement `OpenSearchClient` for document storage.
- [x] Set up APScheduler jobs in FastAPI lifespan to run periodic ingestion tasks.

### Phase 3: Core Logic & Processing
- [ ] Parse GitLab webhooks or scheduled polls to build timeline event streams.
- [ ] Cross-match Jira task IDs with GitLab branch names.
- [ ] Build Confluence auto-linking logic (string matching & manual overrides).
- [ ] Process Confluence docs: chunking, embedding generation (OpenAI), and OpenSearch ingestion.

### Phase 4: AI & RAG Pipeline
- [ ] Build LangGraph workflow for RAG querying.
- [ ] Implement Langchain/OpenAI integrations to query OpenSearch indices.
- [ ] Expose chat/query endpoint in FastAPI.

### Phase 5: UI/UX & Frontend
- [ ] Replace basic JS with a more robust framework if needed, or build complex Vanilla JS views.
- [ ] Implement Timeline UI (vis.js or similar).
- [ ] Implement Sprint/Task dashboard.
- [ ] Implement RAG Chat interface.
