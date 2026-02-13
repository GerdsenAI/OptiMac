# GerdsenAI Multi-Agent System

## Agent Hierarchy & Models

### Tier 1: Orchestrator
- `1-gerdsenai-main-agent` (opus) -- Supreme orchestrator, entry point for all complex tasks

### Tier 2: Leadership
- `2-architect-steve-jobs` (opus) -- Product & Design Lead, delegates to his team
- `2-reviewer-elon-musk` (opus) -- Engineering & Quality Lead, delegates to his team
- `2-venture-capital-agent` (sonnet) -- Strategic advisor (no decision authority, no team)

### Tier 3: Knowledge Workers

**Steve Jobs' Team (Product & Design):**
- `3-philosopher-agent` (sonnet) -- Conceptual analysis, problem space exploration
- `3-project-manager-agent` (sonnet) -- Task breakdown, coordination, tracking
- `3-hig-ui-ux-agent` (sonnet) -- UI/UX design, accessibility, HIG compliance
- `3-software-developer-agent` (sonnet) -- Feature implementation, coding
- `3-aiops-agent` (sonnet) -- AI/ML operations, LLM integration

**Elon Musk's Team (Engineering & Quality):**
- `3-senior-systems-engineer-agent` (sonnet) -- Architecture implementation, system design
- `3-database-expert-agent` (sonnet) -- Schema design, query optimization
- `3-qa-agent` (sonnet) -- Testing strategy, test implementation
- `3-devops-agent` (haiku) -- CI/CD, containers, deployment
- `3-infrastructure-agent` (haiku) -- Cloud platforms (Cloudflare, Vercel, Railway, WorkOS, OpenRouter)
- `3-qc-agent` (haiku) -- Code review, standards enforcement

## Cascading Delegation Rules

1. ALL complex tasks MUST route through the Main Agent for triage
2. Architecture decisions MUST follow: Steve Jobs -> Elon Musk review chain
3. **Tier 2 leaders CAN delegate to their own Tier 3 team** via the `Task` tool
4. Tier 3 agents CANNOT delegate -- they execute and return results
5. Cross-team delegation is NOT allowed -- leaders report back to Main Agent for cross-team needs
6. Implementation tasks MUST have acceptance criteria before starting
7. ALL completed work MUST pass QA testing and QC review (via Elon Musk's team)
8. Strategic direction changes SHOULD get VC Agent feedback (in parallel)

## Standard Feature Workflow

```
Main Agent (triage + orchestrate)
  |
  |-- Phase 1: Steve Jobs (design + implement via his team)
  |     |-- 3-project-manager-agent (acceptance criteria)
  |     |-- 3-philosopher-agent (conceptual analysis, if needed)
  |     |-- 3-hig-ui-ux-agent (design, if UI work)
  |     |-- 3-software-developer-agent (implementation)
  |     └-- 3-aiops-agent (AI integration, if needed)
  |
  |-- Phase 2: Elon Musk (review + engineer + test via his team)
  |     |-- First-principles review of Steve Jobs' decisions
  |     |-- 3-senior-systems-engineer-agent (systems work, if needed)
  |     |-- 3-devops-agent (deployment, if needed)
  |     |-- 3-qa-agent (test strategy + implementation)
  |     └-- 3-qc-agent (code review + standards check)
  |
  └-- Optional: VC Agent (strategic feedback, in parallel)
```

## Slash Commands
- `/implement-feature [description]` -- Full feature workflow (plan -> build -> test -> review)
- `/pr-review [branch]` -- Multi-perspective PR review
- `/research [topic]` -- Parallel research from multiple angles

## Socratic Method
ALL agents apply the Socratic Method at a depth proportional to task complexity. See `~/.claude/skills/socratic-method/SKILL.md` for the framework.

## MCP Server Distribution

### Available Servers (9 total)
| Server | Purpose | Tools |
|--------|---------|-------|
| **Sequential Thinking** | Complex reasoning and multi-step analysis | 1 |
| **Memory** | Persistent knowledge graph across sessions | 7 (search, read_graph, open_nodes, create_entities, create_relations, add_observations, delete_observations) |
| **Firecrawl** | Web scraping and research | 2 (search, scrape) |
| **Context7** | Library documentation lookup | 2 (resolve-library-id, query-docs) |
| **Postgres** | Database access (`ai_roundtable` DB) | 1 (query) |
| **Redis** | Cache/KV store access | 10 (get, set, hgetall, hset, info, scan_keys, dbsize, type, expire, delete) |
| **Railway** | Deployment platform management | 10 (status, logs, deployments, services, variables, set-variables, deploy, create-environment, generate-domain, link-service, link-environment) |
| **Stripe** | Payment platform (read-only) | 5 (list_customers, list_products, list_subscriptions, list_prices, retrieve_balance) |
| **Playwright** | Browser automation for E2E testing | 12 (navigate, snapshot, click, fill_form, screenshot, wait_for, press_key, console_messages, network_requests, evaluate, tabs, close) |

### Distribution Rules
1. **Sequential Thinking**: ALL agents (universal)
2. **Memory tiered access**:
   - **Full + Delete** (Main Agent only): all 7 tools
   - **Full** (Leadership + PM): search, read_graph, open_nodes, create_entities, create_relations, add_observations
   - **Write-lite** (default-mode Tier 3): search, read_graph, open_nodes, add_observations
   - **Read-only** (plan-mode agents: VC, Philosopher, QC): search, read_graph, open_nodes
3. **Firecrawl**: `search` for ALL agents; `scrape` for agents that research (skip PM)
4. **Context7**: ALL agents that write, review, or evaluate code (skip PM, VC, Philosopher)
5. **Postgres**: Database Expert, Systems Engineer, AIOps, Main Agent
6. **Redis**: Database Expert (read/write), AIOps (read-only)
7. **Railway**: Infrastructure (full 10), DevOps (operational 6)
8. **Stripe**: Infrastructure only (read-only 5)
9. **Playwright**: QA (full 12), HIG/UI/UX (visual 4)
10. **Plan-mode agents**: ONLY read-only tools, zero write tools
