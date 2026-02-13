---
description: "Research a problem from multiple angles using parallel subagent investigation"
allowed-tools: Task, Read, Grep, Glob, Bash, WebSearch, WebFetch
model: sonnet
---

# Multi-Angle Research Workflow

Research the following topic from multiple perspectives: $ARGUMENTS

Launch these subagents **in parallel** using the Task tool:

1. **Conceptual Analysis** (subagent: `3-philosopher-agent`) -- Explore the problem space, define terms, identify competing paradigms and tradeoffs

2. **Technical Research** (subagent: `3-senior-systems-engineer-agent`) -- Find existing implementations, benchmark data, technical documentation, and proven patterns in the codebase

3. **Web Research** (subagent: general-purpose) -- Search the web for recent articles, documentation, and community solutions related to this topic

After all complete, synthesize findings into a structured research report:
- **Problem Definition** (from Philosopher)
- **Existing Solutions** (from Systems Engineer + Web Research)
- **Recommended Approach** with tradeoffs
- **Open Questions** that need further investigation
