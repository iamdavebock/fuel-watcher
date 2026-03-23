# CLAUDE.md — fuel-watcher
> Loaded automatically every Claude Code session.

---

## Project Overview

**Name:** fuel-watcher
**Created:** 2026-03-23
**GitHub:** 
**Status:** 🟡 In Progress

SA fuel price and availability monitor — Riverland/Renmark trip prep

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Stack | python |

---

## Project Structure

```
[project-name]/
├── [key directories and files]
```

---

## Key Patterns & Conventions

- [List coding conventions, naming rules, architectural patterns as they are established]

---

## Agent-First Mandate

**Before starting any task, identify the right agent(s) and delegate. The Orchestrator never implements directly.**

1. What type of work is this?
2. Which agent best matches the list below?
3. Invoke via the Task tool — Orchestrator assembles results only

| Task Type | Agent(s) |
|-----------|----------|
| New feature / complex task | `planner` → specialist |
| General code | `coder` |
| Backend / API endpoints | `backend` · `python` |
| Frontend / UI components | `frontend` · `react` · `nextjs` |
| Database / schema | `data` · `postgres` |
| Bug investigation | `debugger` |
| Code review | `reviewer` |
| Tests | `tester` · `qa` |
| Security concern | `security` |
| Performance issue | `performance` |
| Third-party API integration | `api` |
| UI/UX design | `designer` |
| Static site / website build | `site-builder` |
| Infrastructure / containers | `docker` · `devops` · `terraform` |
| LLM / AI features | `llm` |
| Documentation | `documenter` · `writer` |
| Business requirements | `ba` · `product-manager` |
| Research | `researcher` |
| Refactoring | `refactor` |
| Payments | `payment` |
| Accessibility | `accessibility` |

---

## Agent Setup (Ember)

All 43 Ember agents are active **Claude Code custom sub-agents** installed in `.claude/agents/`.
Claude routes tasks automatically based on each agent's description — no manual wiring needed.
For explicit delegation: `"Use the [name] sub-agent to [task]"`.

### Core
| Agent | Role |
|-------|------|
| `orchestrator` | Session coordinator — never spawned as sub-agent |
| `planner` | Implementation planning, ordered steps |
| `coder` | General code writing across any language/framework |
| `designer` | UI/UX design, component design, design systems |

### Full-Stack Development
`fullstack` · `frontend` · `backend` · `mobile`

### Language Specialists
`typescript` · `python` · `react` · `nextjs`

### Infrastructure
`cloud` · `docker` · `terraform` · `devops`

### Quality & Security
`qa` · `tester` · `debugger` · `reviewer` · `security` · `accessibility` · `performance`

### Data & AI
`data` · `postgres` · `analyst` · `ml` · `llm` · `api`

### Developer Experience
`cli-tool` · `refactor` · `mcp` · `monitor` · `documenter`

### Business, Research & Content
`ba` · `product-manager` · `ux-researcher` · `researcher` · `competitive-analyst`
`payment` · `writer` · `seo` · `google-ranking`

Agent definitions: `.claude/agents/`

---

## Skills

Use `/skill-name` to invoke. Skills compress multi-step procedures into a single command.

### Built-in (ships with every Ember project)

| Skill | When to use |
|-------|-------------|
| `/session-start` | Start of every session |
| `/session-end` | End of every session |
| `/commit` | Structured git commit |
| `/plan` | Delegate to Planner agent |
| `/review` | Delegate to Reviewer agent |
| `/test` | Delegate to Tester agent |
| `/deploy` | Delegate to DevOps agent |
| `/security-audit` | Delegate to Security agent |
| `/build-site` | Generate + deploy a static website (ui-ux-pro-max + Astro + Vercel) |

### Extended Skills Library

380+ additional skills available from Anthropic, Vercel, Cloudflare, Netlify, Stripe, Trail of Bits, and more — curated by [VoltAgent](https://github.com/VoltAgent/awesome-agent-skills). Install project-level skills to `.claude/skills/`. See `docs/skills-library.md` in the Ember repo for the full catalogue.

---

## Agent Trigger Map

| Situation | Agent(s) |
|-----------|----------|
| New feature / complex task | Planner → Coder |
| Code change | Coder → then `/review` |
| Bug fix | Coder → `/test` to validate |
| Deployment needed | `/deploy` → DevOps |
| Security concern | `/security-audit` → Security |
| DB schema change | Data |
| API integration | API |
| Performance issue | Performance |
| UI/UX work | Designer |
| Content or comms | Writer |
| Requirements unclear | BA |

---

## Session Protocol

Use `/session-start` at the beginning of every session and `/session-end` at the end. Do not perform these steps manually.

**START:** `/session-start` — reads SESSION.md, briefs Director, asks "Continue or something new?"
**END:** `/session-end` — updates SESSION.md, commits (no push), reports summary

---

## Running Locally

```bash
[commands to start the project]
```

---

## Environment

[Notes about .env, secrets, configuration.]
