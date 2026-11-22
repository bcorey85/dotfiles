# Acceptance criteria

1. Change notes written under the notes paths after a logged branch review leave that review covering the tree; a
   code change still makes it stale. (Phase 1)
2. A finding whose first named path has a directory part and no line number keeps that path as its location; a path:line inside quotes or
   backticks later in the text is not used, and such a finding is not skipped as "not in the tree". (Phase 2)
3. An accepted ask with no location whose change names no file is refused with a request for a `modified:` change
   that names what to change; the coder text of a taken ask names the file. (Phase 3)
4. Accepting an approval-file revert ask restores the file to its text from before the fix pass that made the edit,
   not to HEAD: uncommitted user lines remain and the coder edit is gone. (Phase 4)
5. A fix pass that wants a CLAUDE.md change ends with a user-only ask carrying the wanted change and an untouched
   file. (Phase 5)
6. The loop's reviewer reports reach the run folder without a coder dispatch and without swapping the reviewer agent
   type: the dispatch lines give the exact prompt and say who writes each report: `code_wait.py review` on the code-fork
   route, the main session on the `reviewer_dispatch.py wait` route. (Phase 6)
7. A reviewer question that names a user-owned criterion stops for the user once, with the question and the criterion
   named; a session ruling on it is refused; the user's answer is on the findings row with who and when, and the
   phase asks read as ruled. (Phase 7)
8. A ruling that names a test-only edit is classed as a change, and the fixer applies it in the same round; a plain
   "no code change" ruling still reads as no code. (Phase 8)
9. A launch that finds a live loop on the same worktree started by another skill refuses with a message naming that
   loop, and never stops it silently; a same-skill relaunch still replaces its own loop. (Phase 9)
10. The session-start notice prints no dispatch action for a loop from another branch or detached for a code fork;
    every loop it names carries its age and branch. (Phase 10)
11. A fix pass that removes a comment line no finding names gets the line put back and an ask filed for the
    removal. (Phase 11)
12. When a fix coder ends abnormally, the loop records the findings it was given and the partial diff, the stop note
    names the unverified findings, and the next launch re-dispatches them. (Phase 12)
13. A recorded acceptance of a named pre-existing scoped failure lets the loop pass that failure; an unaccepted or new
    failure still blocks, and the blocker stop prints the accept command. (Phase 13)
14. `bash tests/run.sh` passes.
