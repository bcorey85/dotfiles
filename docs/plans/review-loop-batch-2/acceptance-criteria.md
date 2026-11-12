# Acceptance criteria

- **AC1** — A failed Write of the review handoff or fix findings file cannot start a fix loop on the previous run's file: launch deletes the run-folder inputs it read, so the next launch reads only a file written after the last one. (Phase 1)
- **AC2** — A new launch for a repo stops the older live loop of that repo; loops of other repos keep running. (Phase 1)
- **AC3** — The asks findings file and files outside the run folder are never deleted by launch. (Phase 1)
- **AC4** — asks-done's unknown-outcome error tells the fork that a "leave it" option takes `rejected`, which logs no change and prints no fix launch line. (Phase 2)
- **AC5** — The adopt handoff carries each carried finding and the plan impact whole, with no 800-character cut, and a test asserts a long finding reaches it whole. (Phase 3)
- **AC6** — After a reviewed tree is split across commits, each later commit of that tree keeps review credit; an edit made after review does not. (Phase 4)
- **AC7** — `bash tests/run.sh` passes.
