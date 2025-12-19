---
name: git-workflow
description: Git commit and branching workflow for this project. Use when committing code, creating branches, or opening PRs. Enforces task-based commits, phase branches, and professional commit messages.
---

# Git Workflow

This project follows a strict git workflow tied to `PROGRESS.md` task tracking.

## Branching Rules

- **One branch per phase** in `PROGRESS.md`. All work for tasks in that phase must happen on that phase branch.
- **No direct commits to `main`** for normal work. Integrate phase work via PR only.
- **Branch naming convention:** `phase-<number>-<short-slug>` (example: `phase-5-llm-layer`)

## Task Commit Rules

After finishing **each task** in `PROGRESS.md`:

1. Stage all files changed for that task
2. Commit with a clear, task-referenced message
3. Keep the working tree clean before starting the next task
4. Include `PROGRESS.md` checkbox updates in the same commit

### Commit Message Format

```
Task X.Y — Short description of changes
```

Example:
```
Task 5.2 — Create Prompt Templates
```

### Commit Message Requirements

- Focus on the technical changes made
- Be professional and descriptive
- **NEVER mention AI agents (Claude, GPT, etc.) in commit messages**

## Phase PR Rules

After completing **all tasks in a phase** (per `PROGRESS.md`):

1. Open a PR from the phase branch into `main`
2. Ensure PR meets the pre-commit checklist and CI requirements
3. Request review before merge

## Examples

### Good Commit Messages
- `Task 1.2 — Create Core Enums`
- `Task 4.5 — Implement Stage 3 - Retrieval Index`
- `Fix type annotation in parser module`

### Bad Commit Messages
- `WIP` (not descriptive)
- `Changes` (too vague)
- `Claude helped me fix this` (mentions AI)
- `Task 1.2` (no description)
