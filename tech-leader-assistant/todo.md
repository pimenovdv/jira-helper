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

### Phase 1-6: Foundation, Ingestion, Pipeline & Completed Features
- [x] Foundation & Architecture (uv, Docker, FastAPI structure, Dummy frontend/backend)
- [x] Data Clients (GitLab, Jira, Confluence, Neo4j, OpenSearch) & APScheduler
- [x] Processing & RAG Pipeline (Cross-matching, Confluence chunks, OpenSearch embeddings, LangGraph Agent RAG router, UI views)
- [x] Cross-Service Intelligence (Release Readiness, Release Notes Gen, Stale Branch Cleanup, Code Review Bottlenecks, Coverage/Gap Analysis, Developer Velocity, Auto Code Review)

### Phase 7: Advanced RAG & Agentic Workflows (Agentic RAG & Deep Research)
- [x] **Agentic RAG Tools Implementation**:
    - [x] Create Langchain Tool for **Jira API** to execute JQL queries and fetch task status/details.
    - [x] Create Langchain Tool for **GitLab API** to search repositories, commits, and Merge Requests.
    - [x] Create Langchain Tool for **Confluence API** (global search) using CQL.
    - [x] Integrate existing OpenSearch semantic chunk search as a Tool.
- [x] **Agentic RAG Router**: Develop a smart routing agent capable of deciding which Tool(s) to call based on the user's prompt (e.g., direct API query vs semantic chunk search).
- [x] **Deep Research Workflow (LangGraph)**:
    - [x] Implement **Agent-Planner**: Capable of breaking down complex prompts into a tree of sub-tasks.
    - [x] Implement **Worker Agents**: Specialized agents capable of executing tasks using the Agentic RAG tools.
    - [x] Implement **Agent-Reviewer**: To evaluate worker outputs and initiate retry loops if the data is insufficient or incorrect.
    - [x] Implement robust **State Management** in LangGraph to track execution history, sub-task status, and synthesize the final report.
