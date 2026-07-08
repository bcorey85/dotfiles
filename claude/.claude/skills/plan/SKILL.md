---
name: plan
description: Unified planning front door. Use whenever the user wants to plan a feature, ticket, or nontrivial change and has NOT named a specific planning lane — e.g. "plan this", "/plan TICKET.md", "how should we build X", "spec this out". Classifies the task against the planning-lane routing table, recommends /q-plan vs /eng-spec vs bare /code with the matched rule, confirms with ONE question, dispatches the chosen lane, and logs the routing decision. Do NOT use when the user explicitly invokes /q-plan, /eng-spec, or /code themselves — respect the direct call.
allowed-tools: [Bash, Read, Glob, Grep, AskUserQuestion, Skill]
---

# Plan — routing front door

This skill does NOT plan anything itself. It decides — with the user — which
planning lane a task belongs to, then hands off. It exists because lane
misroutes are asymmetric: sending deep work down the fast lane silently strips
protections from exactly the tickets that need them (the miss is invisible
until something ships), while fast work down the deep lane merely costs ~2×
tokens. That asymmetry is why the recommendation is ALWAYS confirmed, never
silently applied.

## Step 1: Gather the task context

Same conventions as `/eng-spec` Phase 1: use what's already in the thread
(a `/pull-ticket` result, a pasted description). If the skill argument is a
path to a ticket/spec file, read it. If no context is apparent, ask: "What
are we planning? Describe the feature or paste a ticket."

## Step 2: Read the routing table

Read `~/.claude/docs/planning-lanes.md` — the canonical routing table (the
"Current routing" section). It evolves as eval evidence accrues; reading it
at runtime means this skill never goes stale. If that file is missing, fall
back to the "Planning" bullet in `~/.claude/CLAUDE.md`. Do not substitute a
remembered version of the table for the file — the file wins.

## Step 3: Classify

Match the task against the table's triggers. Two kinds:

- **Text-detectable** (judge from the ticket + a quick look at the codebase
  surface if needed): external enforcement-tool config changes;
  reclamation/liveness/teardown work (reapers, sweeps, GC, session/instance
  lifecycle); and whatever else the table lists. Below-lane checks too: a
  well-defined small task with no design decisions → bare `/code`; genuinely
  exploratory ("not sure what we want yet") → suggest plan mode instead of a
  lane.
- **User-facts** (stakes, familiarity of the surface): you cannot infer
  these reliably. State the assumption you're making in the recommendation
  ("assuming this is a familiar surface and normal stakes") so the user can
  correct it with one click rather than being silently misrouted.

## Step 4: Recommend and confirm — one question

Ask ONE AskUserQuestion. The recommended lane goes first, labeled
"(Recommended)", with the matched rule quoted in its description — the user
should see WHICH rule fired, not just the verdict. Offer the other lane,
bare `/code`, and plan mode as alternatives. Do not ask follow-up questions
after the answer; do not re-argue if the user picks against the
recommendation — their override is signal, and it gets logged as such.

## Step 5: Log, then dispatch

Log BEFORE dispatching (declined recommendations are the most valuable data
— they measure whether auto-routing would ever be safe):

```bash
~/.claude/skills/plan/scripts/log_route.sh \
  "<ticket slug or short title>" "<recommended lane>" "<matched rule, short>" \
  "<chosen lane>" "<agreed: true|false>"
```

Then dispatch the chosen lane via the Skill tool, passing the original
argument through (e.g. `/q-plan TICKET.md`, `/eng-spec TICKET.md`). For bare
`/code` or plan mode, say so and let the user proceed — don't dispatch a
coder from here.

Once the lane starts, this skill's job is over. The log lives at
`~/.claude/data/plan-routing.jsonl`; `/review-stats` can join it against
`/escape lane=` tags to measure routing quality (recommended vs chosen vs
outcome).

## Boundaries

- Never silently auto-route — the confirm question is the point of the skill.
- Never plan, research, or dispatch coders from here.
- One log line per invocation, even when the user picks "Other".
