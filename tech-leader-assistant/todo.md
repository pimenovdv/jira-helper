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
- [x] Parse GitLab webhooks or scheduled polls to build timeline event streams.
- [x] Cross-match Jira task IDs with GitLab branch names.
- [x] Build Confluence auto-linking logic (string matching & manual overrides).
- [x] Process Confluence docs: chunking, embedding generation (OpenAI), and OpenSearch ingestion.

### Phase 4: AI & RAG Pipeline
- [x] Build LangGraph workflow for RAG querying.
- [x] Implement Langchain/OpenAI integrations to query OpenSearch indices.
- [x] Expose chat/query endpoint in FastAPI.

### Phase 5: UI/UX & Frontend
- [x] Replace basic JS with a more robust framework if needed, or build complex Vanilla JS views.
- [x] Implement Timeline UI (vis.js or similar).
- [x] Implement Sprint/Task dashboard.
- [x] Implement RAG Chat interface.

### Phase 6: Future Feature Ideas (Cross-Service Intelligence)
- [x] **Release Readiness Dashboard**: Automatically map a Jira Release to its associated tasks, and check if all feature branches (named by task IDs) have been merged into the release branch (named by release ID) in GitLab. Show a "Ready for Release" status.
- [x] **Automated Release Notes Generator**: Fetch all tasks in a Jira Release, fetch their summaries/descriptions, and cross-reference with Confluence documentation to draft release notes. Publish the draft directly to Confluence.
- [x] **Stale Branch Cleanup Assistant**: Identify feature branches in GitLab that are older than X days and correspond to Jira tasks that are already marked as 'Done' or 'Closed'. Provide a 1-click option to delete these stale branches.
- [ ] **Code Review Bottleneck Detector**: Analyze GitLab MR approvals against Jira active sprint timelines. Highlight tasks where the MR has been open for > 2 days but the Jira task is still in "In Progress" or "Code Review" to identify blockers.
- [x] **Completed Items**: Release Readiness Dashboard, Automated Release Notes Generator, Stale Branch Cleanup Assistant, Code Review Bottleneck Detector.
- [ ] **Test Coverage & Documentation Gap Analysis**: Link GitLab test execution results to Jira tasks. If a task is done but its branch lacks new tests or related Confluence pages (auto-linked by feature), flag it as a potential technical debt.
- [ ] **Developer Velocity Metrics**: Analyze Jira task completion time against GitLab commit/MR activity to identify periods of low velocity and suggest possible causes based on Confluence meeting notes or external blockers.
- [ ] **Automated Code Review Assistant**: Integrate an LLM agent to automatically review new MRs in GitLab against organizational coding guidelines stored in Confluence, providing early feedback before human review.

### Phase 7: Advanced RAG & Agentic Workflows (Agentic RAG & Deep Research)
- [x] **Agentic RAG Tools Implementation**:
    - [x] Create Langchain Tool for **Jira API** to execute JQL queries and fetch task status/details.
    - [x] Create Langchain Tool for **GitLab API** to search repositories, commits, and Merge Requests.
    - [x] Create Langchain Tool for **Confluence API** (global search) using CQL.
    - [x] Integrate existing OpenSearch semantic chunk search as a Tool.
- [ ] **Agentic RAG Router**: Develop a smart routing agent capable of deciding which Tool(s) to call based on the user's prompt (e.g., direct API query vs semantic chunk search).
- [ ] **Deep Research Workflow (LangGraph)**:
    - [ ] Implement **Agent-Planner**: Capable of breaking down complex prompts into a tree of sub-tasks.
    - [ ] Implement **Worker Agents**: Specialized agents capable of executing tasks using the Agentic RAG tools.
    - [ ] Implement **Agent-Reviewer**: To evaluate worker outputs and initiate retry loops if the data is insufficient or incorrect.
    - [ ] Implement robust **State Management** in LangGraph to track execution history, sub-task status, and synthesize the final report.
