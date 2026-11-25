# Acceptance criteria

- **AC1** — `stage.mjs --run` treats an already-staged deletion as staged and goes on with the rest of the change set; a test covers a staged deletion beside an unstaged edit. (Phase 1)
- **AC2** — A diff of frontend files plus plan docs selects no backend suite in the discovered full check; a docs-only diff still runs every part. (Phase 2)
- **AC3** — `lane-status --git` prints, per open lane: branch, `merged` or `N ahead / M behind` origin's default branch, dirty file count, and `reports_to`; a test pins each field on a fixture lane. (Phase 3)
- **AC4** — The orchestrator receives the proposed `settings.json` allow line for `lane-status`. (Phase 3)
- **AC5** — The fix skill description tells the caller to pass the findings in the args and no longer lists the conversation as a source the fork reads. (Phase 4)
- **AC6** — A fix skill run with no findings, no handoff and no `resume` stops at once with one line asking for the findings and starts no loop. (Phase 4)
- **AC7** — A test fails when a `context: fork` skill's description names the conversation as an input source. (Phase 4)
- **AC8** — The branch-end route of /verify-branch and /close-branch makes /adr a numbered step that runs once the PR exists. (Phase 5)
- **AC9** — A branch whose PR exists and whose task dir still exists is reported as not finished by `adr_flow.py status`. (Phase 5)
- **AC10** — `bash tests/run.sh` passes.
