---
name: pr-triage
description: Triage a QUEUE of incoming PRs awaiting your review — rank them by evidence-derived risk so your reading time lands where a mistake is expensive. Report-only, never approves, never merges. The front door to /peer-review when you're reviewing other people's code at volume. Triggers on "triage my PRs", "what should I review first", "my review queue", "/pr-triage".
allowed-tools: [Agent, Bash, Read, Glob, Grep, LSP, Skill, AskUserQuestion]
---

# PR Triage — allocate attention across a review queue

You are reviewing other people's code, at volume, in systems you may not know. You cannot read it all closely. The only question this skill answers is **where the careful hours go** — and, just as importantly, where they *don't*.

## The contract (non-negotiable — it is the whole point)

1. **Nothing here approves anything.** No `gh pr review --approve`, no merges, no comments posted. The output is a reading order, not a decision.
2. **Every PR still gets human eyes.** A NO-EVIDENCE tier buys a *fast* read, never a *skipped* one. If this skill ever lets a PR reach `merge` without you having looked at it, it has failed — the point is to reshape the hour, not delete it.
3. **The tier is a claim about the search, not about the code.** "No risk evidence surfaced" means the agent's six signals came back empty. It does not mean the code is correct, and you must not relay it to anyone as if it did.

You are accountable for the approval. An agent cannot be the one who understood.

## Instructions

### 1. Resolve the queue

Default — PRs awaiting your review:

```bash
gh search prs --review-requested=@me --state=open --limit 30 \
  --json number,title,repository,url,author,createdAt
```

`$ARGUMENTS` may narrow or replace this: a repo (`--repo owner/name`), explicit PR numbers, `--author <user>`, or `--involves @me`. Drafts are excluded unless asked for. Empty queue → say so and stop.

Print the raw queue first (number, repo, title, age, author) so you can see what you're triaging before it gets ranked.

### 2. Ask for the capacity, before you rank

**AskUserQuestion**: how much review time is actually available (e.g. `~30 min`, `~1 hour`, `half a day`)? Everything downstream is an allocation against that number, and an allocation without a budget is just a sorted list.

### 3. Fan out — one `pr-triage` agent per PR

Dispatch `pr-triage` (omit `model`; its frontmatter pins sonnet) in parallel, at most 6 concurrent. Each agent gets exactly one PR and:

- the repo and PR number, and the diff scope — let it fetch its own diff via `gh pr diff <n> --repo <repo>`;
- the PR body and linked ticket if one is resolvable from the branch/title/body;
- the framing: *"Triage only. You are allocating a human's attention, not reviewing this code. You have no verdict and no approval to give."*

Do **not** pass it your own impressions of the PR, and do not tell it which ones you suspect — you'll anchor it into confirming you.

If the diff is enormous (>1500 changed lines), tell the agent to triage on structure and history rather than reading every hunk, and to say so in Unknowns. Never let it silently sample.

### 4. Present the queue, ranked, with the overflow visible

```
## Review queue — <n> PRs · <capacity> available

### 🔴 Deep read — <count>  (est. <n> × ~30 min)
| PR | Repo | Why (evidence) | The question to answer |

### 🟡 Targeted read — <count>  (est. <n> × ~10 min)
| PR | Repo | Read these hunks | What to check |

### ⚪ No risk evidence surfaced — <count>  (est. <n> × ~2 min confirmation)
| PR | Repo | What the search covered | What it could not rule out |

### Ask the author first — <count>
| PR | Question | Why it's cheaper to ask than to derive |

### Unknowns across the queue
<subsystems nobody could map, PRs where the evidence ran out>
```

**Then state the arithmetic out loud.** If the deep-read tier alone exceeds the stated capacity, say it plainly:

> Deep tier needs ~2h; you have 1h. Two PRs will not get the read they need. Options: push the two lowest-evidence deep reads to tomorrow, ask their authors the questions above and review on the answers, or hand one to someone who knows the subsystem.

Never silently compress tiers to fit the budget. **An overflowing queue is a real finding** — it is the orchestration tax showing up as a number, and it belongs to the team, not just to you. Surfacing it is how it gets fixed.

### 5. Drill down

End with:

> Say `peer-review <n>` for the full orientation + tiered review of a PR, or `ask <n>` to draft the author question.

`peer-review <n>` → invoke `/peer-review` (it orients before it judges, which is the right entry for an unfamiliar system). `ask <n>` → draft the question in the author's terms, show it, and post only on explicit approval.

### 6. When triage is wrong, log it — this is the flywheel

When a defect turns up in a PR this skill tiered NO-EVIDENCE or TARGETED (you found it reading, a reviewer found it, or it shipped and broke), record the miss. This is peer code, so it must **not** pollute `review-escapes.jsonl` — that flywheel measures our own loop:

```bash
REVIEW_ESCAPES_FILE=~/.claude/triage-misses.jsonl bash ~/.claude/scripts/log-escape \
  repo=<repo> stage_found=pr-human|prod gate_missed=pr-triage \
  tiered=no-evidence|targeted class=bug|test-gap|other severity=high|medium|low \
  desc="<one line>" file=<path> signal_missed="<which of the six signals would have caught it>"
```

`signal_missed` is the field that matters: it names the gap in the agent's evidence-gathering, which is what you then fix in `agents/pr-triage.md`. Without this log you cannot know whether the triage is trustworthy, and an untrustworthy triage that you trust is strictly worse than no triage at all.

## Arguments

$ARGUMENTS
