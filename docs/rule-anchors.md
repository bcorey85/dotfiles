# Rule anchors

Every heading block of the prompt files listed below has a content hash and the
reason it exists. `claude-doctor` recomputes the hashes and reports two faults: a
block with no row, and a row whose block no longer exists. Whitespace does not move
a hash.

The prompt files never carry this provenance. It lives here, and the change ledger
(`agent-evals.md`) holds the full story behind each evidence kind.

To change an anchored block:

1. Edit the prompt file.
2. Run `~/.claude/scripts/rule-anchors.sh list <file>` and copy the new hash.
3. Replace the row's hash. Set `evidence` and `reason` to what backs the new text.
4. Run `claude-doctor`. Git history keeps the old rows.

Evidence kinds: `gate ranking`, `census`, `removal round`, `seeded round`,
`controlled replay`, `judgment` (nobody measured it), `unproven` (never exercised).

| hash     | file                                   | section                                                     | evidence     | reason                                                                                                                                                                               |
| -------- | -------------------------------------- | ----------------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 7e052009 | agents/code-reviewer.md                | (preamble)                                                  | seeded round | Dispatch contract: name, description, tools, project memory. The opus pin stays because sonnet at this gate missed planted defects that the same prompt caught on opus.              |
| 2f8b49b6 | agents/code-reviewer.md                | ## Calibration (shared)                                     | census       | Points at the shared calibration file by section name, so five reviewers share one bar. A rename left three adopters pointing at nothing once.                                       |
| e967af14 | agents/code-reviewer.md                | ## Do NOT Flag                                              | judgment     | Suppression list. Its four specialist-ownership bullets were kept in every arm tested. The rest is under test: a reviewer without it caught the same keyed regressions with zero false findings in one replicate at opus. A second replicate decides removal. |
| 19a920b9 | agents/code-reviewer.md                | ## Do Flag                                                  | judgment     | Defect-class checklist. The REST checks inside it fire only when a route, write, or validator is in the diff (census). Under test with the block above.                              |
| 9411a7fc | agents/code-reviewer.md                | ### Step 1: Determine Scope                                 | judgment     | How the reviewer finds the diff: the handoff block first, else the git working state. Kept in every arm tested.                                                                      |
| 9ef6991a | agents/code-reviewer.md                | ### Step 2: Read the Changes                                | judgment     | Read every file in scope. The two read instructions were kept in every arm tested. Its three required audits (sibling analysis, silent degradation, contract against implementation) and its two guard sentences are under test with the judgment blocks. |
| d4c92c16 | agents/code-reviewer.md                | ### Step 3: Categorize Findings                             | judgment     | Applies the shared disposition rule and drops unreachable paths. Under test with the judgment blocks.                                                                                |
| 170c1b19 | agents/code-reviewer.md                | ## Output Format                                            | judgment     | The report template the dispatcher parses: summary headings, prior issues, Fix/Ask/Nit. The differential-comparison requirement was cut earlier as a retired line of attack.         |
| 94f9730a | agents/code-reviewer.md                | ## Reviewer-Specific Tool Use                               | judgment     | Verify by running the code, not by reading alone. Kept in every arm tested.                                                                                                          |
| f02667dc | agents/code-reviewer.md                | ## Self-Check Before Reporting                              | judgment     | Pointer to the shared self-check. Under test with the judgment blocks.                                                                                                               |
| 36de7dd1 | skills/_shared/reviewer-calibration.md | # Reviewer Calibration (single source of truth)             | census       | Names the adopting reviewers and warns that a renamed section breaks them. The warning failed once, which is why the doctor now checks the references.                               |
| b4ab6a17 | skills/_shared/reviewer-calibration.md | ## Persistent Memory                                        | unproven     | Project memory of known patterns. Never exercised: every review round dispatches without a memory directory.                                                                         |
| 0d9c6962 | skills/_shared/reviewer-calibration.md | ## Calibration Anchor                                       | census       | The merge-blocking question and the examples that set the bar's height. Under test: inert on recall and false findings in one replicate at opus.                                     |
| e79a8d75 | skills/_shared/reviewer-calibration.md | ## Verify the Premise Before Flagging                       | judgment     | Check the code, the rule, and the diff before a finding ships. Under test with the block above.                                                                                      |
| a20c02f1 | skills/_shared/reviewer-calibration.md | ## Disposition                                              | census       | One disposition per finding, and the routing of a borderline item to the place the self-check names. Under test with the block above.                                                |
| 5b08c8b2 | skills/_shared/reviewer-calibration.md | ## Self-Check Before Reporting                              | judgment     | The calibration question run once more per finding. Under test with the block above.                                                                                                 |
| 8fdd8aff | skills/_shared/code-vocabulary.md      | # Code Vocabulary (what may never appear in committed code) | judgment     | The boundary between the private operator workflow and the shipped tree. Loaded by the reviewer and by every coder.                                                                  |
| e616ade4 | skills/_shared/code-vocabulary.md      | ## The rule                                                 | judgment     | Bans pipeline vocabulary (phase numbers, decision ids, plan paths, process narration) from committed code.                                                                           |
| f9f922c6 | skills/_shared/code-vocabulary.md      | ## What to write instead                                    | judgment     | A comment says what the code cannot say, not where the decision was made.                                                                                                            |
| 32b8f59e | skills/_shared/code-vocabulary.md      | ## Sweep before handing back                                | judgment     | Diff-check against the banned table before reporting. Under test in the reviewer: the contract-only arm did not load this file.                                                      |
