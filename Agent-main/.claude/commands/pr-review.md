---
description: "Multi-perspective pull request review: code quality, security, UX, and strategic fit"
allowed-tools: Task, Read, Bash, Grep, Glob
model: sonnet
---

# Pull Request Review Workflow

Review the current changes (or PR specified by: $ARGUMENTS) from multiple perspectives.

## Step 1: Identify Changes
Run `git diff` (or `git diff main...HEAD`) to identify all changed files and the scope of the PR.

## Step 2: Quality Control Review
Use the `3-qc-agent` subagent to perform a thorough code review covering correctness, security, performance, maintainability, and standards compliance.

## Step 3: QA Assessment
Use the `3-qa-agent` subagent to assess test coverage for the changes. Identify untested paths and suggest additional tests.

## Step 4: UI/UX Review (if applicable)
If the changes include frontend or user-facing modifications, use the `3-hig-ui-ux-agent` subagent to review accessibility, responsiveness, and design consistency.

## Step 5: Strategic Review
Use the `2-venture-capital-agent` subagent to provide brief strategic feedback on whether this change moves the product in the right direction.

## Step 6: Synthesis
Compile all reviews into a single PR review summary with:
- **Verdict**: Approve / Request Changes / Needs Discussion
- Critical issues (blocking)
- Warnings (should address)
- Suggestions (optional improvements)
- Positive highlights
