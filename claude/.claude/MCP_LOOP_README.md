# MCP Loop — How-To Guide

A structured, MCP-embedded development workflow with two distinct loops: **PM** (spec owner) and **Dev** (code owner). The Jira ticket is the contract between PM and dev — PM writes it, dev reads it.

---

## MCP Server Setup

All four MCP servers are configured via the helper script at `~/dotfiles/scripts/mcp_auth`. It handles OAuth vs PAT auth and scope flags.

```bash
# OAuth servers (Jira, Notion, Figma) — opens browser for auth
mcp_auth jira          # user scope (default)
mcp_auth notion
mcp_auth figma

# PAT server (GitHub) — prompts for token
mcp_auth github

# Override scope if needed
mcp_auth jira --scope local
```

**Transport:** All servers use HTTP (`--transport http`). SSE is deprecated in Claude Code 2.0.10+.

**Session expiry:** Jira sessions potentially expire after ~2 hours (community-reported, not consistently observed). Re-run `mcp_auth jira` if you hit auth errors.

**Verify:** `claude mcp list` to confirm all servers are connected.

---

## Architecture Overview

### Role-Based MCP Access

| Role | Reads From | Writes To |
|------|-----------|-----------|
| PM | Notion (specs), Figma (mockups) | Notion (specs, docs, changelog), Jira (tickets) |
| Dev | Jira (tickets, AC), Figma (mockups) | GitHub (code, PRs), Jira (transitions only), Notion (eng-arch → Wiki) |

The default path: **devs pull from Jira, not Notion**. The Jira ticket has everything needed (summary, AC, link to Notion spec for optional deep-dive). This cut dev-loop MCP calls by ~50%. Devs *can* read Notion directly if they need deeper spec context — it's just not the efficient default. Devs also push `eng-arch/` docs to the Notion Wiki via `/push-arch`.

### Three-Tier Artifact System

| Tier | Location | Owner | Synced to Notion? | Purpose |
|------|----------|-------|--------------------|---------|
| Product specs | `PM_WORKSPACE/product-specs/` | PM | Yes (Specs DB) | What/why |
| Eng plans | `eng-plan/` (in repo) | Dev | No (local only) | How (per-ticket) |
| Eng architecture | `eng-arch/` (in repo) | Dev | Yes (Wiki) | How (cross-cutting) |

### MCP Servers

| Server | Transport | Primary Role | Notes |
|--------|-----------|-------------|-------|
| Jira | HTTP (`https://mcp.atlassian.com/v1/mcp`) | Both loops | Sessions expire ~2hr. Carries 74% of all MCP calls. |
| Notion | HTTP (`https://mcp.notion.com/mcp`) | Primarily PM loop | Specs DB, Docs, Wiki, Changelog. Devs use for `/push-arch` and optional spec deep-dives. |
| Figma | HTTP (`https://mcp.figma.com/mcp`) | Both loops (frontend) | Rate limits on free plan (6 calls/month) |
| GitHub | HTTP (`https://api.githubcopilot.com/mcp`) | Rarely used | `gh` CLI displaces it for most operations |

---

## PM Loop

**Owner:** PM (spec side)
**Tools:** Notion MCP (read/write) + Jira MCP (write)
**Goal:** Turn a feature idea into structured Jira tickets with full context.

### Pipeline: `/feature-plan` → `/publish-spec` → `/create-ticket`

### Step 1: `/feature-plan <feature description>`

Runs a multi-agent research and planning pipeline to produce a comprehensive product spec.

**What happens:**
1. **Product spec agent** defines the problem, user stories, success criteria, scope
2. **Research phase** (mandatory) — identifies 3-5 pivotal questions, runs web searches for best practices, flags findings that contradict initial assumptions
3. **User checkpoint** — presents spec + research for approval before continuing
4. **UX researcher + Backend architect** run in parallel — UX recommends patterns/flows, backend defines data models and API contract
5. **Frontend architect** designs UI against UX recommendations + API contract
6. **Writes `product-specs/<feature-name>.md`** — unified spec document

**Output:** A comprehensive spec file at `PM_WORKSPACE/product-specs/<feature-name>.md`

**Key lesson:** Always research before architecture. 5 minutes of web search prevents 10 bad tickets. The "pivotal questions" pattern — ask "what 3-5 questions, if answered wrong, would invalidate this design?" — then research them.

### Step 2: `/publish-spec [feature name or spec file]`

Publishes the local product spec to Notion's Specs DB.

**What happens:**
1. Finds the source — either a `product-specs/*.md` file or a brief description
2. Extracts and condenses into Notion template format: Problem → Approach → AC → Jira Tickets → Open Questions
3. Creates a page in the Specs DB (`notion-create-pages`) with Status: "Draft"
4. Asks the user to review and suggests `/create-ticket` as next step

**Notion template sections:** Problem, Approach, Acceptance Criteria, Jira Tickets (placeholder), Open Questions

### Step 3: `/create-ticket [spec name or Notion page ID]`

Reads a Notion spec and creates Jira tickets from its acceptance criteria.

**What happens:**
1. Finds the Notion spec (by name search or page ID)
2. Extracts each acceptance criterion → each becomes a Jira Task
3. Creates tickets via `createJiraIssue` (description as **markdown string**, NOT ADF JSON)
4. Updates the Notion spec: sets `Jira Key` property, fills the "Jira Tickets" section, changes Status from "Draft" to "Ready"
5. Presents the created tickets and suggests: "Dev can now `git checkout -b PROJ-XX-description` and run `/pull-ticket`"

**Highest-ROI MCP workflow:** One `/create-ticket` run turned a Notion spec into 10 structured Jira tickets. Cross-system workflow that Claude reasons through — genuinely painful to do manually.

### Post-Ship: `/notion-docs` + `/changelog`

After the dev ships and merges:

**`/notion-docs <what to document>`** — Creates or updates customer-facing docs in Notion's Docs section (Getting Started, API Reference, Guides).

**`/changelog [version]`** — Adds a changelog entry to the Notion Changelog DB. Gathers changes from git history, categorizes as Feature/Fix/Improvement/Breaking.

### PM Loop Summary

```
/feature-plan "task filtering"     → writes product-specs/task-filtering.md
/publish-spec                      → publishes to Notion Specs DB (Status: Draft)
/create-ticket                     → reads Notion spec, creates Jira tickets, updates spec (Status: Ready)
                                   ↓
                     [Dev implements — see Dev Loop below]
                                   ↓
/notion-docs                       → updates customer-facing docs after merge
/changelog v0.3.0                  → adds changelog entry to Notion
Update spec status → Implemented   → via Notion MCP directly
```

---

## Dev Loop

**Owner:** Dev (code side)
**Tools:** Jira MCP (read) + Figma MCP (read, if frontend) + `gh` CLI (write)
**Goal:** Turn a Jira ticket into a shipped, reviewed PR.

### Pipeline: `/pull-ticket` → `/pull-design` → `/eng-plan` → `/code` → `/peer-review` → `/commit` → `/verify-changes` → `/pr`

### Step 0: Create the branch

**Option A — Manual:**
```bash
git checkout -b PROJ-XX-short-description
```

**Option B — `/create-branch` (recommended):**
```
/create-branch PROJ-20                       → fetches ticket summary, builds branch name, bases off main
/create-branch PROJ-20 off Sprint-A-2026     → explicit ticket + sprint branch base
/create-branch my-experiment                  → no ticket, custom name off main
```

`/create-branch` does more than `git checkout -b`: it fetches the Jira ticket summary to auto-name the branch, creates an empty init commit (required by GitHub to open a PR), pushes, and opens a draft PR via `/pr +draft` so the team can track changes from the start.

Branch naming convention: `JIRAPROJECT-TICKETNUMBER-short-description` (e.g., `PROJ-14-task-detail-modal`)

For work without a Jira ticket: `feature-short-description` or `fix-short-description`

### Step 1: `/pull-ticket`

Fetches the Jira ticket for the current branch. This is the entry point to the dev loop.

**What happens:**
1. Reads the branch name, extracts the Jira ticket key (e.g., `PROJ-14`)
2. Fetches the ticket via `getJiraIssue` — summary, description, AC, status
3. **Auto-transitions**: If status is "To Do" → automatically invokes `/move-ticket in progress` (no confirmation)
4. Presents the ticket context: key, summary, status, AC, suggested approach

**Auto-invocation:** `/move-ticket in progress` (via Skill tool)

**Design note:** The efficient default is Jira only — the ticket description has everything needed. Devs *can* read Notion for deeper spec context, but it's rarely necessary.

### Step 2: `/pull-design [figma-url]` (Frontend only)

Extracts Figma design context before architecture/implementation. **Run before `/eng-plan`** so the architect has design measurements.

**What happens:**
1. Finds the Figma URL — from arguments, Jira ticket description, or asks the user
2. Parses the URL for `fileKey` and `nodeId`
3. Checks for cached design tokens (`eng-arch/design-tokens.md`) — if cached, runs in lightweight diff mode (only reports NEW or CHANGED tokens)
4. Calls `get_design_context` and `get_variable_defs` from Figma MCP
5. Presents a **Design Brief**: measurements, tokens, component inventory, visual decisions, data model gaps, and any conflicts with the eng plan or ticket AC

**Precedence rule:** Ticket AC > Figma for behavior; Figma > ticket for visual measurements.

**Tip:** Select one frame at a time. Full pages produce noisy output.

### Step 3: `/eng-plan [modifiers] [description]`

Plans the implementation. Consumes whatever context is already in the conversation thread (from `/pull-ticket`, `/pull-design`, or user description).

**What happens:**
1. **Gathers context** — uses thread context, checks for existing eng plan in `eng-plan/`
2. **Assesses scope** — frontend, backend, or fullstack. Accepts `be`/`fe`/`fs` modifiers.
3. **Launches architect agent(s)** — based on scope:
   - Backend only → `backend-architect`
   - Frontend only → `frontend-architect`
   - Fullstack → `backend-architect` first (for API contract), then `frontend-architect` with that contract
4. **Presents decisions and questions** — tradeoffs, ambiguities, convention questions. Waits for answers.
5. **Asks TWO mandatory questions** (hard gate — does NOT proceed without answers):
   - "Save to disk?" → writes to `eng-plan/PROJ-XX-description.md`
   - "Implement now?" → dispatches coder subagent(s)

**If implementing:** Dispatches `backend-coder` and/or `frontend-coder`, then auto-invokes `/peer-review`.

**Key rule:** A well-written ticket is NOT a reason to skip the architect. Tickets describe the PM's approach; architects validate against real code.

**Auto-invocation:** `/peer-review` (if coders dispatched)

### Step 4: `/code [modifiers] <task description>`

Dispatches coder subagent(s) without architectural planning. Use for straightforward implementation where the plan is already clear.

**Modifiers:**
- `be`/`fe`/`fs` — force scope
- `+fast` — Haiku model (trivial changes)
- `+deep` — Opus model (complex tasks)

**What happens:**
1. Determines scope (auto-detect or from modifier)
2. Dispatches `backend-coder` and/or `frontend-coder` subagents
3. Summarizes what was implemented
4. **Auto-dispatches `/peer-review`** (passes through `+fast`/`+deep` modifier)

**When to use `/code` vs `/eng-plan`:** Use `/code` when the approach is clear. Use `/eng-plan` when design decisions are needed.

### Step 5: `/peer-review [modifiers]`

Reviews recent changes using the `code-reviewer` subagent. This is the quality gate between implementation and commit.

**Modifiers:** `+fast` (Haiku), `+deep` (Opus)

**What happens:**
1. Checks modified file count
2. If 5 or fewer files → single reviewer. If more → parallel reviewers (frontend + backend)
3. Reviews for: bugs, security, performance, style, missing error handling, anti-patterns, architectural violations
4. Presents results by severity
5. Suggests next steps: `/fix-feedback` if issues found, `/commit` if clean

**Auto-invoked by:** `/code`, `/fix`, `/refactor`, `/fix-feedback`, `/eng-plan` (when coders dispatched)

**Target:** 1 review round for standard features, 2 max for complex ones.

### Step 5b: `/fix-feedback [modifiers]` (If review found issues)

Dispatches coder subagents to fix valid review findings.

**What happens:**
1. Parses review feedback, categorizes as frontend or backend
2. Dispatches appropriate coder(s) with the specific issues
3. Coders include a **caller-check**: if a fix changes a method signature or return type, all callers are updated in the same pass
4. **Auto-dispatches `/peer-review`** after fixes complete

### Step 6: `/commit [modifiers]`

Creates a commit and pushes. User MUST stage files first — Claude never stages.

**What happens:**
1. Checks staged changes (`git diff --cached`)
2. Notes any unstaged changes (informational only)
3. Drafts commit message: `PROJ-XX: description` if branch has ticket key, else conventional commit format
4. Commits and pushes (unless `+no-push` modifier)

**Important:** No `Co-Authored-By` trailers. User stages, Claude commits.

### Step 7: `/verify-changes`

Verifies implementation against eng-plan checklist and Jira ticket AC. Final quality gate before PR.

**What happens:**
1. Finds the eng plan and extracts verification checklist
2. Pulls Jira ticket AC via `getJiraIssue`
3. Gets the branch diff
4. **Runs the full test suite** (most important step) — blocker if tests fail
5. **Runs build/type-check** — catches issues tests miss
6. **Runs lint/format check** — non-blocking but reported
7. Verifies each checklist item (test-verified > build-verified > code-verified)
8. Marks items as PASS / WEAK PASS / FAIL / PARTIAL / SKIP
9. Reports coverage gaps and uncovered changes

**Key rules:**
- Never says "all checks pass" if any item was verified by file reading alone
- Tests can pass while the build is broken — always run both
- WEAK PASS = code looks correct but has no test coverage

### Step 8: `/pr [modifiers]`

Creates the pull request and transitions the Jira ticket.

**Modifiers:** `+draft` (draft PR, no Jira transition), `--base <branch>` (custom base)

**What happens:**
1. Resolves base branch (from `--base`, existing PR, or default to `main`)
2. Gathers context — status, commits, diff, branch name
3. Checks for existing PR (converts draft → ready if applicable)
4. Analyzes ALL commits for PR description
5. Creates PR via `gh pr create` with title `PROJ-XX: description`
6. **Auto-invokes `/move-ticket in review`** (non-draft only, no confirmation)

**Auto-invocation:** `/move-ticket in review` (via Skill tool)

### Dev Loop Summary

```
git checkout -b PROJ-XX-description
/pull-ticket                        → fetches Jira ticket, auto-moves To Do → In Progress
/pull-design                        → extracts Figma measurements (frontend only, before eng-plan)
/eng-plan                           → runs architect(s), asks questions, optionally implements
/code                               → dispatches coder(s), auto-runs /peer-review
/peer-review                        → reviews changes, suggests /fix-feedback or /commit
  └─ /fix-feedback                  → fixes issues, auto-re-runs /peer-review
/commit                             → stages, commits, pushes
/verify-changes                     → tests + build + checklist verification
/pr                                 → creates PR, auto-moves In Progress → In Review
```

---

## Supporting Skills

### Bug Fixing

**`/fix [be/fe/fs] [+fast/+deep] <bug description>`** — Analyzes a bug, determines scope, dispatches coder(s) to fix it. Auto-invokes `/peer-review`.

**`/refactor [+fast/+deep] <description>`** — Dispatches coder(s) for refactoring. Auto-invokes `/peer-review`.

### Architecture & Documentation

**`/eng-arch [be/fe/fs] [+quick/+deep]`** — Generates or updates system architecture docs. Runs architect agents, diff+merges with existing docs.

**`/push-arch`** — Pushes an `eng-arch/*.md` doc to Notion Wiki. This is the dev's path into Notion — architecture decisions that span multiple tickets become shared team references.

### Caching (`/cache-*` commands)

MCP calls have latency, rate limits, and session expiry. When the data is stable (rarely changes between sessions), caching it locally eliminates redundant API calls and makes dependent skills faster.

The pattern: a `/cache-*` skill pulls data once via MCP, writes it to a local file, and downstream skills read the local file first — only falling back to MCP on cache miss.

**`/cache-design-tokens`** — Pulls the full design system from Figma (colors, typography, spacing, shadows, component inventory) and caches to `eng-arch/design-tokens.md`. Run once per project, or when the design system changes. Without the cache, every `/pull-design` run does a full extraction. With the cache, `/pull-design` runs in lightweight diff mode — only reporting what's new or changed in the target frame vs the cached system.

**`/cache-jira-transitions`** — Pulls available Jira board transitions via `getTransitionsForJiraIssue` and writes the status → transition ID mapping to `PROJECT_ROOT/JIRA.md`. Transition IDs are stable (To Do=11, In Progress=21, In Review=31, Done=41) — they don't change unless the board workflow is reconfigured. Without the cache, every `/move-ticket`, `/pull-ticket`, and `/pr` invocation would need an API call to look up the transition ID. With the cache, those skills read `PROJECT_ROOT/JIRA.md` directly — zero MCP calls for the common case. `/move-ticket` auto-invokes this on cache miss (status not found in the table).

### Testing

**`/test <description>`** — Dispatches the right coder subagent to write tests.

**`/test-review [be/fe/fs]`** — Reviews test suites for coverage gaps, weak assertions, stale tests.

### Workflow Utilities

**`/move-ticket <status>`** — Transitions Jira ticket. Used internally by `/pull-ticket` and `/pr`. Can also be called directly for ad-hoc transitions (e.g., `/move-ticket done`). Reads cached transition IDs from `PROJECT_ROOT/JIRA.md` — zero MCP calls in the common case.

**`/investigate <issue>`** — Read-only diagnosis. Explores an issue without making changes.

**`/explain <code path>`** — Step-by-step code explanation for beginners.

**`/create-branch [ticket-key] [off base-branch]`** — Creates a feature branch (auto-names from Jira ticket summary if a ticket key is provided), creates an empty init commit, pushes, and opens a draft PR via `/pr +draft`. Accepts an optional `off <base>` to branch from a sprint branch instead of `main`.

**`/migrate`** — Detects the ORM/migration tool and runs migrations.

### Meta

**`/cloptimize [+deep/+quick] [focus area]`** — Meta-reflection. Analyzes the current conversation for friction, corrections, and missed opportunities. Recommends concrete edits to skill files, agent definitions, CLAUDE.md, and MEMORY.md. Never applies changes without user approval.

**`/save-note <content>`** — Saves a note to the Obsidian vault at `~/vault`.

---

## Auto-Invocation Map

Skills chain into other skills automatically. The orchestrator (parent skill) invokes follow-up skills — subagents cannot invoke skills themselves.

| Trigger Skill | Auto-Invokes | Condition |
|--------------|-------------|-----------|
| `/pull-ticket` | `/move-ticket in progress` | Ticket is in "To Do" |
| `/code` | `/peer-review` | After all coders complete |
| `/fix` | `/peer-review` | After all coders complete |
| `/refactor` | `/peer-review` | After all coders complete |
| `/fix-feedback` | `/peer-review` | After all coders complete |
| `/eng-plan` | `/peer-review` | After coders dispatched + complete |
| `/pr` | `/move-ticket in review` | Non-draft PRs only |

**Manual triggers (never auto-invoked):** `/commit`, `/pr`, `/verify-changes` — these are user decision points.

---

## When to Skip the PM Loop

| Work Type | PM Loop? | Jira Ticket? | Example |
|-----------|----------|-------------|---------|
| Product features | Full PM loop | Yes (from spec) | "Add task filtering" |
| Infrastructure / DX | Skip PM loop | Yes (direct Task) | "Add Docker", "CI/CD pipeline" |
| Experiments / spikes | Skip both | No | Throwaway branches, "let me try something" |

**Infrastructure tickets** skip Notion entirely. Create a Jira Task directly, then use the full dev loop from `/pull-ticket` onward.

---

## Git Conventions

**With Jira ticket:**
- Branch: `PROJ-XX-short-description`
- Commit: `PROJ-XX: description`
- PR title: `PROJ-XX: description`

**Without ticket:**
- Branch: `feature-short-description` or `fix-short-description`
- Commit: conventional format (`type(scope): description`)

**Never:** `Co-Authored-By` trailers. This overrides Claude Code's default behavior.

---

## Key Lessons Learned

### MCP vs Local
- **If you have the data locally, don't use MCP.** Grep, git log, file reads — all faster and free.
- **MCP shines for cross-system workflows.** Jira ticket → code → PR that references it.
- **`gh` CLI completely displaced GitHub MCP** for solo dev. MCP would be useful for cross-repo search in a team setting.
- **Jira transition IDs are stable** — cached in `PROJECT_ROOT/JIRA.md`, zero API calls for common transitions.

### Workflow Patterns
- **Encapsulate flaky MCP calls into skills.** When Claude gets an API call wrong repeatedly, wrap it in a skill. The skill becomes the correctness boundary.
- **Defense in depth for enforcement.** Three layers: skill-level (strongest), CLAUDE.md (backup), MEMORY.md (context shaping). Use strong gating language: "STOP", "hard gate", "Do NOT proceed."
- **Auto-invoke mechanical steps, keep decision points manual.** Ticket transitions = auto. Commit/PR/verify = manual.
- **Research before architecture.** The pivotal questions pattern prevents rework downstream.
- **Backend architect as API contract auditor.** Even for frontend-only specs, run the backend architect to READ actual code. Specs can diverge from reality.

### Quality
- **1 review round target.** Push quality upstream (architect checklists, coder pre-submission checks) instead of catching everything at review time.
- **`/peer-review` = code quality.** Bugs, patterns, security.
- **`/verify-changes` = AC completeness.** Does it do what the ticket says?
- **Tests can pass while the build is broken.** Always run both.
- **Never report "all checks pass" if verification was file-reading only.** Be honest about confidence levels.

---

> **Footnote: Design vs Ticket Tension**
>
> Figma mockups and Jira ticket AC will diverge. Figma shows visual details the ticket doesn't mention (hover states, spacing, empty states). Tickets specify behavior Figma can't express (debounce timing, error handling, rollback logic). Sometimes they actively contradict each other (Figma shows a save button, ticket says auto-save on blur).
>
> **Precedence rule:** Ticket AC wins for behavior, Figma wins for visual measurements. When silent (Figma shows something, ticket doesn't mention it), implement as shown unless it conflicts with the data model.
>
> **The expensive discovery:** These divergences are cheapest to resolve at spec time (PM loop) and most expensive at implementation time (dev loop). If the dev discovers 10 conflicts mid-`/code`, they have to stop, analyze each one, decide precedence, and potentially re-plan. `/pull-design` surfaces these gaps explicitly — run it before `/eng-plan` so the architect can account for them, not after.
>
> **The ideal (aspirational):** The PM extracts Figma context during `/create-ticket` and bakes a Design Brief into the ticket description — measurements, visual decisions, and a divergence table with resolutions. This way the dev gets complete context from `/pull-ticket` alone, and `/pull-design` becomes a validation step rather than a discovery step. This flow isn't fully automated yet but is the direction we're heading.

> **Footnote: MCP Usage Logging**
>
> Optionally, you can track MCP tool calls for usage analysis. We batch-log all calls at PR time (not mid-session) to `docs/mcp-usage.jsonl` — one JSON object per line:
> ```jsonl
> {"ts":"2026-02-21T19:46:38Z","server":"jira","tool":"getJiraIssue","context":"pulled PROJ-14 ticket context"}
> ```
> Only MCP tool calls are logged (Jira, Notion, Figma, GitHub) — not `gh` CLI or local tools. Include failures with `"error": true`. This data is useful for spotting wasteful call patterns (e.g., we found 13 avoidable `getTransitionsForJiraIssue` calls, which led to caching transition IDs locally in `PROJECT_ROOT/JIRA.md`).
