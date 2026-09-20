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
- [x] Phases 1-59: Initial setup, core sync, DB, RAG workflows, code quality automations, assorted Jira/GitLab/Confluence reminders and checks, Confluence stale documentation archiver, Jira unassigned bug reminder, GitLab MR missing description reminder, Jira epic completion checker, Jira too many subtasks warning, Jira unassigned epic warning, and GitLab MR secrets scanner.

### Phase 60: Confluence Empty Page Checker
- [x] Create `confluence_empty_page_checker_task` to scan Confluence spaces for pages that are essentially empty (less than 50 characters of text after stripping HTML).
- [x] Add a warning comment to the page tagging the last author and advising them to add content or delete the page.
- [x] Include an auto-generated HTML marker `<!-- AUTO_GENERATED_EMPTY_PAGE_WARNING -->` to avoid duplicates.
