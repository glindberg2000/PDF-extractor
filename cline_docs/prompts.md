# Reusable Prompts (Shared)

- [Prompt 1: Describe a common cross-role task.]
- [Prompt 2: Another reusable prompt for all roles.]

# Prompts and Communication Protocol

## Shared Docs Communication Protocol

- The canonical protocol for sharing and syncing docs is defined in `.windsurf/rules/08-shared-docs-communication.md` (always present in session payloads).
- **Summary:**
  - Write docs in `cline_docs_shared/`.
  - To sync docs to all team containers/sessions:
    - Click the **Propagate** button in the Shared Docs UI, **or**
    - Call the API: `POST /api/team/{teamId}/cline_docs_shared/propagate` (e.g. `curl -X POST http://localhost:8000/api/team/PDF_Extractor/cline_docs_shared/propagate`)
  - Announce changes in chat if important.
  - See the full rule for details and best practices.

## Team Communication Protocol for Shared Docs

To share and sync documentation (markdown files) across all team members and sessions, we use git. Please follow these steps:

### Adding a New Doc
1. Create your file in `teams/PDF_Extractor/cline_docs_shared/`
2. `git add <filename>`
3. `git commit -m "Add <filename>"`
4. `git push`
5. Announce in chat: "Added <filename> to shared docs!"

### Getting New Docs
- If you have no local changes: `git pull`
- If you have local changes:
  - `git add . && git commit -m "WIP"` (or `git stash`)
  - `git pull`
  - (if stashed) `git stash pop`
- To get just one file:
  - `git fetch`
  - `git checkout origin/main -- teams/PDF_Extractor/cline_docs_shared/<filename>`

### Referencing Docs in Chat
- Use: `@cline_docs_shared:<filename>`
- Example: "See @cline_docs_shared:productContext.md for the latest requirements." 