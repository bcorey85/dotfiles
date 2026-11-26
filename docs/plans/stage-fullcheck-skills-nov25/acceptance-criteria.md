# Acceptance criteria

- **AC1** — `stage.mjs --run` treats an already-staged deletion as staged and goes on with the rest of the change set; a test covers a staged deletion beside an unstaged edit. (Phase 1)
- **AC2** — A diff of frontend files plus Markdown plan docs selects no backend suite in the discovered full check; only Markdown under docs/ is skipped (a non-Markdown file there, such as `docs/openapi.yaml`, still widens the check); a Markdown-only diff still runs every part. (Phase 2)
- **AC3** — `lane-status --git` prints, per open lane: branch, `merged`, `no commits` (the branch tip is older than the lane's start) or `N ahead / M behind` origin's default branch, dirty file count, and `reports_to`; a test pins each field on a fixture lane. (Phase 3)
- **AC4** — The orchestrator receives the proposed `settings.json` allow line for `lane-status`. (Phase 3)
- **AC5** — The fix skill description tells the caller to pass the findings in the args and no longer lists the conversation as a source the fork reads. (Phase 4)
- **AC6** — A fix skill run with no findings, no handoff and no `resume` stops at once with one line asking for the findings and starts no loop. (Phase 4)
- **AC7** — A test fails when a `context: fork` skill's description names the conversation as an input source. (Phase 4)
- **AC8** — The branch-end route of /verify-branch and /close-branch makes /adr a numbered step that runs once the PR exists. (Phase 5)
- **AC9** — A branch whose PR exists and whose task dir still exists is reported as not finished by `adr_flow.py status`. (Phase 5)
- **AC10** — `bash tests/run.sh` passes.
- **AC11** — A user timer samples the top memory holders (RSS by command and herdr workspace) every minute into a rotating file; a test feeds a fake process table and checks the sample. (Phase 6)
- **AC12** — `lane-status` names finished idle lanes with their Claude RSS; a test feeds a fake process table and checks it. (Phase 6)
