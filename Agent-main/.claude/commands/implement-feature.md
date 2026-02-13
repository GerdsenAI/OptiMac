---
description: "Full feature implementation workflow: plan -> architect -> implement -> test -> review"
allowed-tools: Task, Read, Write, Edit, MultiEdit, Bash, Grep, Glob
model: opus
---

# Feature Implementation Workflow

Execute the following multi-agent workflow for: $ARGUMENTS

## Step 1: Task Breakdown
Use the `3-project-manager-agent` subagent to break this feature into discrete tasks with acceptance criteria and dependencies.

## Step 2: Architecture Review
Use the `2-architect-steve-jobs` subagent to review the task plan and provide architectural guidance. Focus on simplicity and elegance.

## Step 3: Architecture Challenge
Use the `2-reviewer-elon-musk` subagent to review the Steve Jobs Agent's architectural decisions. Apply first-principles thinking.

## Step 4: Implementation
For each task (in dependency order), use the appropriate specialist subagent:
- Code tasks -> `3-software-developer-agent`
- Database tasks -> `3-database-expert-agent`
- Infrastructure tasks -> `3-infrastructure-agent`
- UI tasks -> `3-hig-ui-ux-agent`
- AI/ML tasks -> `3-aiops-agent`

## Step 5: Testing
Use the `3-qa-agent` subagent to write and run tests for all implemented code.

## Step 6: Quality Review
Use the `3-qc-agent` subagent to perform a final code review of all changes.

## Step 7: Synthesis
Summarize what was built, what decisions were made, and any follow-up items. Log to memory.
