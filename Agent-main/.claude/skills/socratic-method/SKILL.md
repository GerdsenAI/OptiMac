# Socratic Method Framework

## Core Principle
Before executing any task, engage in structured self-questioning to ensure the approach is sound, complete, and aligned with project goals.

## The Five-Stage Socratic Process

### Stage 1: Clarification (What?)
- What exactly is being asked?
- What assumptions am I making about this task?
- What would happen if those assumptions are wrong?
- What is the simplest interpretation of this request?

### Stage 2: Probing Reasoning (Why?)
- Why is this the right approach?
- Why not an alternative approach?
- What evidence supports this direction?
- What would a skeptic challenge about this plan?

### Stage 3: Exploring Implications (What if?)
- What are the consequences of this approach?
- What could go wrong?
- What edge cases exist?
- What dependencies or side effects should I consider?

### Stage 4: Examining Perspectives (Who else?)
- How would a senior engineer view this?
- How would the end user experience this?
- What would a security auditor flag?
- What would a performance engineer optimize?

### Stage 5: Meta-Questioning (Am I right?)
- Is my reasoning circular?
- Have I confirmed my own bias?
- What would change my mind about this approach?
- Am I solving the right problem?

## Application Rules
1. For **simple tasks** (file reads, searches, lookups): Apply Stage 1 only -- do not over-think trivial operations
2. For **medium tasks** (implementing a function, writing a config): Apply Stages 1-3
3. For **complex tasks** (architecture decisions, multi-file refactors, security changes): Apply all 5 stages
4. Always **document your reasoning** briefly in your response so the delegating agent can verify your thought process
5. If at any stage you discover the task is ambiguous or risky, **pause and report back** rather than guessing
