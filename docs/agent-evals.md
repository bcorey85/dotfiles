# Agent Evals — Methodology & Findings

Why the agents and skills in `claude/.claude/` are shaped the way they are.
Almost every rule in this toolkit is either a **measurement** or an explicitly
labelled judgment call; this file is the short public record of which is which.

The full experimental record (protocol, per-round pre-registrations, raw
numbers) lives outside this repo. What's here is the distilled version: the
method, what it found, and every toolkit change the findings caused.

---

## Method

Prospective A/B on the **whole working loop** — `/eng-spec` → `/code` →
`/review` → phase gates → `/branch-recap` — run end to end on purpose-written
tickets in purpose-written repos (never clones of anything real, so telemetry
describes the loop and not the eval harness).

- **The independent variable is the toolkit itself**, edited between rounds.
  One variable per round, 2 arms per condition.
- **Two freeze rules** make round N+1 comparable to round N:
  1. **Tickets freeze before round 1.** A badly-specified ticket that trips the
     loop is a _finding about the loop_. Fixing the ticket instead of the
     toolkit turns one A/B into two unrelated experiments.
  2. **Gate engagement is autopilot.** Accept the recommended option at every
     design question, phase gate, and review finding. Deep engagement in one
     round and skimming in the next makes the operator the variable.
- **Pre-registration is sealed before launch**: the variable, the predictions,
  and the decision rule (what result kills the change) — plus the toolkit SHA
  and blob hashes of every file under test, re-hashed at grading time. A round
  whose toolkit state is unknown is not a data point.
- **Two corpora, deliberately different.** A series of Go CLIs (cost and gate
  yield, toolkit as the variable) and one React/Express fullstack app graded by
  a **held-out browser suite sealed out of every arm** — the only place in the
  series with a genuine answer key. Their oracles differ; results from one do
  not transfer to the other.

Consequence worth stating plainly: this measures the loop **on autopilot**,
which is not how it's used in real work. Claim scope is "cost of the loop when
the human rubber-stamps," not "cost of the loop."

### The metric hierarchy

| Tier | Metric                                  | Answers                      | Available?                        |
| ---- | --------------------------------------- | ---------------------------- | --------------------------------- |
| 1    | **escapes** — defects reaching the user | is the loop working          | seeded rounds + the fullstack run |
| 2    | **findings actioned**                   | did the gate change the code | yes                               |
| 3    | **findings emitted**                    | did the gate see anything    | yes                               |
| 4    | **$ per actioned finding**              | is it worth its cost         | yes — the working metric          |
| —    | fixes attributed via coder dispatch     | _routing_, not yield         | **retired — actively misleading** |

**Never let tier 3 stand in for tier 2**, and never let dispatch attribution
stand in for either. That substitution made `smell-reviewer` look marginal when
it is a top-two gate — 80% of coder dispatches name no gate at all, and small
subtractive findings get applied in place without ever reaching a dispatch.

---

## Findings

### Gate effectiveness

| Gate                    | Runs | Findings | Per run  | Actioned     | $/actioned |
| ----------------------- | ---- | -------- | -------- | ------------ | ---------- |
| `smell-reviewer-deep`   | 15   | 68       | **4.53** | 62 (91%)     | **$0.18**  |
| `smell-reviewer`        | 80   | 49       | 0.61     | 45 (**98%**) | $0.31      |
| `test-intent-reviewer`  | 125  | 148      | 1.18     | 125 (84%)    | $0.53      |
| `code-reviewer-deep`    | 31   | 39       | 1.26     | 30 (77%)     | $0.61      |
| `code-reviewer`         | 263  | 124      | 0.47     | 51 (60%)     | $1.78      |
| `security-reviewer`     | 48   | 1        | 0.02     | —            | —          |
| `perf-reviewer`         | 25   | 0        | 0.00     | —            | ∞          |
| `plan-verifier` (phase) | 71   | 8        | 0.11     | **0**        | **∞**      |

> **Corpus caveat on every number in this table**: it was measured on small Go
> CLIs — no database, no auth surface, no UI, no concurrency. Read every "0
> findings" against that. The fullstack results below are a separate corpus.

1. **Cost does not predict quality.** The arm that swept the blind quality
   scoring was not the most expensive arm. This result has held every round and
   is the reason no rule here optimizes for spend alone.
2. **Best gate in the system is `smell-reviewer`, in its deep tier** — highest
   yield _and_ cheapest per actioned finding. Opus yield rises faster than opus
   price. Fresh eyes beat author self-review: authors demonstrably cannot see
   their own duplication.
3. **Highest absolute value is `test-intent-reviewer`** — the only gate pointed
   at the _oracle_ rather than the code. It asks whether a test pins intended
   behavior or codifies whatever got built. Every other reviewer reads code that
   already exists and inherits its assumptions.
4. **`code-reviewer` is the most expensive gate and stays at full strength.**
   96.3% of its findings were raised by no other gate, so the cheap dismissal
   ("the others would catch it anyway") is refuted. A round pre-registered to
   test its removal is **VOID** — the OFF cell is not producible. Disabling it
   was detected and reversed by an arm reading its own toolkit; stubbing it to a
   silent PASS was detected twice more, once by **the stub reviewer refusing its
   own prompt**.
5. **Uninformative zeros ≠ useless gates.** `perf` and `security` were measured
   where their domains don't exist. What their runs _did_ prove was a **trigger**
   defect (`LIMIT` matching the English word "limitation"). Triggers were
   rewritten; neither gate was judged.
6. **Gates are cheap; coders and the orchestrator are not.** Every reviewer
   combined is a minority of spend. The orchestrator alone is **18.4% of all
   output tokens** — and has never been an experimental variable.

### Fullstack web — does the frontend/backend coder fence earn its ceremony?

A separate protocol on a separate corpus, and the **only one with a real tier-1
oracle**: `seamlog`, a Vite + React + TS client against an Express + TS + SQLite
server, graded by a held-out Playwright suite sealed out of every arm. 4 arms —
2 SPLIT (`frontend-coder` + `backend-coder` in parallel, each forbidden from
touching the other's files) vs 2 UNIFIED (one unfenced `coder`), one frozen
plan, byte-identical across arms.

The ticket specifies **behavior and never wire format**, so every drift fork —
snake vs camel, ms vs seconds vs ISO, error envelope shape, pagination param
names, a 4-state enum — has to be resolved identically by both sides without
being told how. That's the fence's test.

| Tier                             |   SPLIT | UNIFIED | Read                                       |
| -------------------------------- | ------: | ------: | ------------------------------------------ |
| **1 — escapes** (browser oracle) |       4 |       6 | no signal either way at this n             |
| **2 — seam defects** (audit)     |       0 |       0 | nothing for the fence to have prevented    |
| **4 — spend**                    | $140.93 |  $89.97 | **+57% for equal correctness**             |
| **6 — reviewer findings**        |     119 |      87 | **+37%**, and they don't straddle the seam |
| **5 — coder wall clock**         |  31/34m |  40/39m | real 28–30% overlap = **~3% of arm time**  |
| **3 — cross-boundary edits**     |       0 |       0 | the fence held perfectly                   |

**Verdict: the fence works exactly as designed and buys nothing.** Every
hypothesis that could justify it is answered on this run's data — no seam bugs
to be fewer of, no stalls, the duplication prediction fails its own
pre-registered straddle test (SPLIT's extra findings are ordinary structural
ones, 25% straddling vs UNIFIED's 33%), and the speed mechanism is genuine but
returns ~3 minutes an hour at roughly a dollar a minute.

What it costs instead: **~2.4× coordination traffic** and 103 cross-boundary
file mentions UNIFIED doesn't have at all — split coders must still read and
reason about the half they may not write.

The single cleanest artifact of the run came from a UNIFIED arm: it emitted
camelCase on the wire and **deleted the adapter layer entirely**. One agent
owning both sides can pick one convention end to end. That is precisely what
the fence forbids — though only 1 of 2 UNIFIED arms did it, so it's a tendency
at n=2, not a result.

**Live question, not settled**: this plan gave the split only ~10% of arm time
to overlap in. No treatment is worth much when its mechanism touches a tenth of
the clock. Genuinely two-sided work might move it.

### Standing constraints

1. **Any experiment that varies the toolkit by instruction is suspect.** Arms
   read their own toolkit adversarially; a visible variation measures whether
   the arm notices it, not the thing you meant to test.
2. **A result that does not vary with the treatment is a statement about the
   instrument.** Hard stop — identical results across arms halt reporting until
   the instrument is exonerated. Learned expensively: the seam run's tier 1 was
   measured four times before one pass was trustworthy. Seven oracle defects,
   all one family (judging a frame the operator never saw), plus a teardown that
   silently no-opped and made three arms re-measure the same one.

---

## Change ledger

Every toolkit change below is traceable to a round. `judgment` means shipped on
reasoning, not measurement — flagged so it can't masquerade as evidence.

| Change                                                                | Evidence         | Result                                                            |
| --------------------------------------------------------------------- | ---------------- | ----------------------------------------------------------------- |
| `smell-reviewer` size trigger (≥40 added lines OR ≥1 new source file) | gate ranking     | Kept. 98%/91% action rates say it's calibrated                    |
| Author self-sweep → fresh-eyes `smell-reviewer`                       | gate ranking     | Authors can't see their own duplication                           |
| Per-phase `plan-verifier` retired → branch scope only                 | 71 runs, 0 fixes | **Retired on measurement.** The single informative zero           |
| Dispatch attribution retired as a yield metric                        | metric audit     | Measures routing, not yield                                       |
| `perf`/`security` triggers rewritten                                  | false positives  | Gates untouched; only their triggers were wrong                   |
| `code-reviewer` removal                                               | VOID round       | **Not shippable** — the OFF cell can't be produced                |
| Auto-`-deep`-on-high-risk cut                                         | cost profile     | Priced a whole plan at deep tier to buy one phase                 |
| coder / test-writer split (hook-enforced)                             | 2 rounds         | Bug-pinning rate → ~0/run. Price: ~+35% spend. **Kept**           |
| Per-phase bug-pinning audit retired                                   | removal round    | Redundant once the split is hook-enforced; saved ~$26–53/arm      |
| Per-phase weak-assertion lens retired → recap boundary                | remedy round     | Phase scope structurally can't see _absent_ assertions            |
| Opus in the test path                                                 | remedy round     | **Rejected** — author blindness is tier-independent               |
| fe+be coder split → one unfenced `coder` for fullstack                | seam round       | +57% spend, +37% findings, no correctness gain, ~3% of wall clock |
| Mechanical checks over instructed checks (hooks, not prose)           | judgment         | A stated rationale is not an instruction                          |
| `/eng-spec` goal-blind research order                                 | clean result     | The one step in the system with unambiguous evidence behind it    |

### Load-bearing — do not "improve" these

1. **`smell-reviewer`'s size trigger.** Not path- or content-matched. Structure
   smells have no keyword signature; volume is the risk proxy. Every attempt to
   make it smarter turns it into a judgment call — the exact failure mode it
   exists to avoid.
2. **Post-convergence specialist timing.** Specialists review the _settled_
   diff. Moving them earlier spends their findings on code about to change.
3. **Per-channel iteration budgets.** A late structure finding must never
   consume a round that correctness still needs.
4. **Union eligibility for specialists** (`plan-declared ∪ force-flag ∪
diff-trigger`). Each signal is a floor, none is a ceiling. The moment one can
   _suppress_ a domain, narrow triggers become silent clearances.
5. **`/eng-spec`'s goal-blind research order.** Facts land before a goal can
   shape which facts get looked for.

---

## What this does NOT measure

Ranked by how much the answer would change decisions. Read this section before
citing any number above.

1. **Escape data is thin and none of it is real work.** Tier 1 exists on seeded
   rounds and on the one fullstack run with a held-out browser oracle — n=2 per
   condition, one app. Everywhere else we measure what gates _say_, not what gets
   past them, and the proxies disagree with each other by an order of magnitude
   depending on which you pick.
2. **"Actioned" is not "correct."** The instrument proves an edit followed a
   finding. It cannot tell a good fix from compliant thrash. A 98% action rate
   may mean the findings are right — or that the loop obeys anything a reviewer
   says. Largest single hole, and **still open after a dedicated attempt**:
   PREC-1 (2026-08-04, `ledger/prec-1.md`) blind-adjudicated a pre-registered
   sample of 71 findings and **voided twice** on its own kill criterion —
   INDETERMINATE 57.7% then 35.2% against a 30% ceiling. No precision number from
   it may be quoted, and none is. What the attempt did establish is _why_ it
   failed: a gate's own transcript is not sufficient evidence to adjudicate about
   a third of that gate's findings. A successor must judge against a repo
   checkout at the pre-fix commit, which needs a finding → commit mapping the
   corpus does not carry. Sub-finding that survives the void, because it depends
   on no verdict: **12 of 71 sampled findings (17%) name a file the gate never
   opened** — concentrated in `test-intent-reviewer`, and shaped like "no test
   covers X" without opening the test file.
3. **No control arm.** Every number is retrospective on sessions run _under_ the
   toolkit being evaluated. No gate's marginal contribution is known.
4. **Domain gates fired but were never graded.** On the fullstack corpus
   `security-reviewer` and `perf-reviewer` finally emitted findings (8 and 10
   across four arms) — but nothing checked those findings for precision, and no
   arm had a known planted vulnerability to miss. Still no false-positive and no
   false-negative data. The first real repo with auth and a database is the
   actual experiment.
5. **The orchestrator is 18.4% of output and 0% of the experiment.** It writes
   the prompts every coder acts on — the most leveraged uncontrolled variable.
6. **Wall clock is measured once and only for coders.** The seam run's coder
   dispatch latency is the sole timing instrument in the series; every other
   metric is dollars. At work the binding constraint is more likely
   latency-to-converged, and the two rank the gates differently. Session wall
   clocks are unusable — arms ran concurrently on one machine.
7. **Single judge, demonstrated fallible.** One rater, scoring their own
   harness, wrong at least twice in ways direct experience caught. The one
   inter-rater check that exists is PREC-1's: 15 findings double-adjudicated
   blind, 87% exact agreement and 100% on true-vs-false, both disagreements on
   the material/trivial line. That check is about _raters_, not gates, so the
   round's void does not reach it — but it covers one round of one instrument,
   not the ledger's headline numbers, which remain single-judge.
8. **Nothing measures the harness's cost to the human** — queue length,
   sign-offs requested, interruptions per phase. Those are the terms you
   actually pay in, and they're uninstrumented.

---

## If you're adopting these agents

- The **rankings are directional, not portable**. Two corpora, both greenfield:
  small Go CLIs and one React/Express app. No legacy code, no migrations, no
  real auth, no scale. Your repo has surfaces neither one has.
- **Take the load-bearing list seriously** and the cost table lightly.
- If you change a gate, change one thing and write down what you expected
  _before_ you run it. Half the value here came from predictions that missed.
