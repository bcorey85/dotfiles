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

| Change                                                                                                                                                                                        | Evidence         | Result                                                                                                                                                                                                                                                                                                                                                  |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `smell-reviewer` size trigger (≥40 added lines OR ≥1 new source file)                                                                                                                         | gate ranking     | Kept. 98%/91% action rates say it's calibrated                                                                                                                                                                                                                                                                                                          |
| Author self-sweep → fresh-eyes `smell-reviewer`                                                                                                                                               | gate ranking     | Authors can't see their own duplication                                                                                                                                                                                                                                                                                                                 |
| Per-phase `plan-verifier` retired → branch scope only                                                                                                                                         | 71 runs, 0 fixes | **Retired on measurement.** The single informative zero                                                                                                                                                                                                                                                                                                 |
| Dispatch attribution retired as a yield metric                                                                                                                                                | metric audit     | Measures routing, not yield                                                                                                                                                                                                                                                                                                                             |
| `perf`/`security` triggers rewritten                                                                                                                                                          | false positives  | Gates untouched; only their triggers were wrong                                                                                                                                                                                                                                                                                                         |
| `code-reviewer` removal                                                                                                                                                                       | VOID round       | **Not shippable** — the OFF cell can't be produced                                                                                                                                                                                                                                                                                                      |
| Auto-`-deep`-on-high-risk cut                                                                                                                                                                 | cost profile     | Priced a whole plan at deep tier to buy one phase                                                                                                                                                                                                                                                                                                       |
| coder / test-writer split (hook-enforced)                                                                                                                                                     | 2 rounds         | Bug-pinning rate → ~0/run. Price: ~+35% spend. **Kept**                                                                                                                                                                                                                                                                                                 |
| Per-phase bug-pinning audit retired                                                                                                                                                           | removal round    | Redundant once the split is hook-enforced; saved ~$26–53/arm                                                                                                                                                                                                                                                                                            |
| Per-phase weak-assertion lens retired → recap boundary                                                                                                                                        | remedy round     | Phase scope structurally can't see _absent_ assertions                                                                                                                                                                                                                                                                                                  |
| Opus in the test path                                                                                                                                                                         | remedy round     | **Rejected** — author blindness is tier-independent                                                                                                                                                                                                                                                                                                     |
| fe+be coder split → one unfenced `coder` for fullstack                                                                                                                                        | seam round       | +57% spend, +37% findings, no correctness gain, ~3% of wall clock                                                                                                                                                                                                                                                                                       |
| Mechanical checks over instructed checks (hooks, not prose)                                                                                                                                   | judgment         | A stated rationale is not an instruction                                                                                                                                                                                                                                                                                                                |
| `/eng-spec` goal-blind research order                                                                                                                                                         | clean result     | The one step in the system with unambiguous evidence behind it                                                                                                                                                                                                                                                                                          |
| Per-finding gate log (silent runs included)                                                                                                                                                   | metric audit     | Aggregate rows carry no `file:line` and no denominator — per-gate yield and marginal contribution were not computable                                                                                                                                                                                                                                   |
| Review loop capped at ONE correctness round; residue defers to branch exit                                                                                                                    | judgment         | Later iterations re-review settled code; a `blocker` is the only exemption                                                                                                                                                                                                                                                                              |
| Severity tiers → `fix` / `ask` / `nit` + orthogonal `blocker` flag                                                                                                                            | 629-run log      | `fixed` (331) > `critical+high` (138) — the tier predicted nothing the loop acted on. Matches Google eng-practices and Conventional Comments                                                                                                                                                                                                            |
| Post-convergence MEDIUM-classification pass deleted                                                                                                                                           | follow-on        | Reviewers label disposition at the point of finding; the pass had nothing left to classify                                                                                                                                                                                                                                                              |
| `code-reviewer` differential-comparison reporting requirement cut                                                                                                                             | prior round      | Required-output changes were retired as a line of attack; this requirement predates the differential patch that was actually measured                                                                                                                                                                                                                   |
| `code-reviewer` REST-specific checks gated on the surface being present                                                                                                                       | census           | Three checks distilled from REST projects fired on every review regardless of stack; now skipped unless a route table, write, or validator is in the diff                                                                                                                                                                                               |
| `code-reviewer` pinned to opus                                                                                                                                                                | seeded round     | Sonnet at this gate missed planted defects the same prompt caught on opus. Raises the price of every review — the most expensive single change in this table                                                                                                                                                                                            |
| Review loop reads the fix diff before it exits                                                                                                                                                | seeded round     | Fixes were never re-read; the pass recovers real defects introduced by the fix itself, at no measurable added cost                                                                                                                                                                                                                                      |
| Fix-diff pass defers to the docs when a fix contradicts them                                                                                                                                  | seeded round     | Without it the reviewer sided with the new code and proposed amending the spec. Reversed on a replant; no false doc-contradiction claims                                                                                                                                                                                                                |
| Review loop stripped of write tools; its one permitted log now goes through a helper                                                                                                          | census           | It held write access for a single sanctioned append and was observed making unsanctioned direct source edits against its own fence. The capability is gone rather than re-forbidden                                                                                                                                                                     |
| Spec defects are now loggable and logged — `gate_missed=eng-spec`, `stage_found=phase-gate`, and a `/code` step-3b rule filing the row when a `FAILING-TEST` resolves as a plan defect        | log gap          | Three same-class defects in one project, **none in the escape log**: the enum had no value for "the plan was wrong", so each fell through to a prose friction file where nothing aggregates it. Also the only class structurally invisible to review — a wrong spec and a faithful diff agree with each other, so the remediation was never on any dial |
| `log-scan`'s `exit=` redefined as did-it-RUN (0 = printed rows, 1 = ran clean, 2 = did not run), `scan=prohibition` added, and `/code` step 2 now runs and logs a plan's prohibition criteria | schema misfit    | The field conflated "ran" with "passed", which is unloggable for any grep-family scan — grep exits 1 on a clean tree. A pass was written as an error row, silently deleting the precision denominator. Both 0 and 1 now require counts                                                                                                                  |
| `load_bearing_clean` excluded from the `nit` telemetry count                                                                                                                                  | field audit      | A packet reporting 1 nit logged `nit:2`; the extra was the clean-file flag. It inflated the field measuring reviewer noise **when a gate came back clean** — the tuning signal pointed the wrong way                                                                                                                                                    |
| Four unexplained rules in the review loop now state the failure they prevent                                                                                                                  | census           | A pass-through telemetry field, the parallel-split threshold, the specialist re-entry cap, and the load-bearing-clean flag could not be defended by anyone; each now names what breaks without it, and the two numeric ones say they are chosen rather than measured                                                                                    |
| The reviewer's rule for a prior issue the fixer skipped now names the failure on both sides, and one duplicated scope instruction was cut                                                     | census           | A second, independently dispatched reading of the same reviewer file found the skip rule stated only half its job — do not re-flag — with nothing said about a rationale that does not hold. It now covers both, and the scope instruction that was stated twice in the same file is stated once                                                        |
| The implementer's reuse rule drops an unsupported superlative, its no-self-audit rule gains a reason, and one duplicated instruction is cut                                                   | census           | Two independently dispatched readings of the implementer's directives both ranked the same claim first — that ignorance of an existing artifact is the most common way junk gets produced, which nothing measures and the nearest result declines to support. The rule keeps its full force and now states the cost it actually imposes                 |
| The phase-boundary decision list in the dispatch skill is repaired, and its forced first-phase stop, its fix-round cap, and its branch-end reconciliation rule all state their reasons        | census           | The list was structurally broken — two items merged onto one line and the numbering repeated — in the list that decides whether the loop stops for a human. Two independent readings both ranked the unexplained stop first and a fact written twice as two editable copies second; the duplicate is now a pointer                                      |
| Three reviewers repointed at the calibration section they were told to adopt, after it was renamed and they were not updated                                                                  | census           | The shared calibration file warns that renaming a section requires updating every agent that names it; the rename happened and three of five adopters were left pointing at a heading that no longer existed. The warning sat three lines from the edit that broke it                                                                                   |
| The calibration file's opening question now routes a borderline finding to the same place its own self-check does, and stops colliding with the reserved label                                | census           | The question sent a worth-mentioning item to a section no reviewer's output format has, while the self-check called the same item the lowest disposition. It also used the word "block" in a sense opposite to the reserved stop-the-phase label defined a few lines below                                                                              |
| The calibration examples now say they set the height of the bar rather than its subject                                                                                                       | census           | Every example is a general code-correctness one, but four of the five reviewers that adopt the section review something else, and one had already grown its own restated copy to work around the mismatch                                                                                                                                               |
| A new check verifies that every calibration section a reviewer names actually exists, firing when either side is edited                                                                       | judgment         | The prose warning it replaces failed once already, silently, and the failure mode is invisible: an agent pointed at a missing heading still produces a plausible review. Reports rather than blocks, because renaming a section is legitimate work and only the unfinished half is the problem                                                          |
| The review wrapper no longer restates the rule for classifying a finding that invalidates a plan, and points at the agent that owns it instead                                                | census           | The two copies had already drifted, and the wrapper's had lost the qualifier limiting the category to a missed external contract — without it, ordinary internal defects route into a modal that blocks until a human answers                                                                                                                           |
| The review loop's gate-critical block now names both exits that may mark the commit gate clean, not just one, and says why the second qualifies                                               | census           | It listed only the convergence exit while the wrapper that actually runs the mark also runs it on the deferral exit — a rule about when commits may proceed, contradicted by the file that operates it. The deferral exit repairs every blocker first and logs the remainder for branch exit, which is what makes it a normal completion                |
| The planning skill's task directory, when there is no ticket key, is now named for the area of the codebase being changed rather than for the change                                          | census           | That path is handed to the agents that research the codebase without being allowed to know the goal, so a descriptive folder name told them the problem, the intended fix, and that current behavior was wrong. It is the one property of the design that nothing downstream can restore once lost                                                      |
| Both files that synthesize the architect's ruled-out approaches now carry the architect's own count instead of asserting three                                                                | census           | The instruction that produces them allows fewer than three if it says so, and the template preserves that; the two files doing the synthesis had lost it, which pressures inventing a third — an invented alternative in a decision record reads later as one genuinely considered and rejected                                                         |
| The two architect descriptions no longer restate the test for skipping design work, and name where the whole test lives                                                                       | census           | The skill's test is a four-part conjunction; the descriptions had it as one part, so they authorized skipping design on changes the skill would have sent to an architect. They stay prose rather than a pointer because they are read when choosing an agent, without the skill loaded                                                                 |
| The finalization phase writes the two self-sufficiency spec sections from the template instead of re-teaching their rules                                                                     | census           | The rules existed in three places — the phase file, the template's own section comments, and the shared decision format for the evidence tags. The phase file's copy was the one no author reads while writing the section                                                                                                                              |
| The threshold below which design work may be skipped now says it is a chosen budget and which way to err near it                                                                              | census           | Two independent readings both flagged it as a bare number with no stated origin, and a reader at the boundary needs the direction to err more than a defense of the value                                                                                                                                                                               |

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
   corpus does not carry — and `ledger/prec-2-feasibility.md` then found that
   mapping unrecoverable (1–5 commits per arm; transcript replay reaches only
   60% fidelity because 726 Bash calls per arm mutate files invisibly). A
   precision instrument now requires a **prospectively instrumented round**, not
   more analysis of this corpus. Sub-finding that survives the void because it
   depends on no verdict — and which was then censused over all 446 findings,
   no sampling, no adjudication (`ledger/cite-census.md`): **one finding in four
   (25.6%) names a file the gate never opened.** By gate: `test-intent-reviewer`
   47.8%, `code-reviewer-deep` 35.0%, `code-reviewer` 30.3%,
   `smell-reviewer-deep` 17.9% — a split by gate _role_, not by model tier.
   Nearly a third of those unchecked citations are `spec.md` or `CLAUDE.md`: the
   gate says "this deviates from the documented behavior" without opening the
   document. This measures evidentiary discipline, **not** correctness — an
   unchecked citation can still be a true finding.
3. **No control arm.** Every number is retrospective on sessions run _under_ the
   toolkit being evaluated. No gate's marginal contribution is known. CONTROL-1
   is pre-registered against this (`control-sealed/PREREG.md`, sealed
   2026-08-04) and **not yet run**: 6 arms × {full loop, `code-reviewer` only,
   no gates}, graded by a held-out acceptance suite no arm ever sees — the only
   tier-1 escape measurement in the plan. Nothing may be cited from it until it
   runs. It also carries the per-dispatch tree snapshots that gap #2's successor
   needs, which is why the two are one round.
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
