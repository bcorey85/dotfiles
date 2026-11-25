# Acceptance Criteria — lane-tools-1123

> Written before implementation. The closing Verify phase reconciles these
> against the test suite.

- **AC1** — The lane viewer starts under a memory cap (for example systemd-run --user --scope -p MemoryMax=1G) or restarts itself past a size, and lane-status names a viewer over the cap. A test starts the launcher and asserts the cap is on the command.
- **AC2** — close with a lane name or worktree path that has no lane file entry finds the herdr workspace whose checkout path matches, checks the branch is merged, and closes it. A test with an empty lane file and a fake herdr workspace list passes.
- **AC3** — A git post-merge hook (or the pull helper) runs check-script-links and restows the scripts package when it reports a gap. A test adds a script on a branch, merges it, and asserts the link exists.
- **AC4** — In a Claude Code Bash call, type ls resolves to the system ls.
- **AC5** — A test or doctor check runs that probe and fails when ls is an alias or function.
- **AC6** — Deletes: nothing.
- **AC7** — A viewer started in a herdr pane and a viewer started from a plain terminal both run under the same memory cap.
- **AC8** — Setting the viewer cap to a different size (for example 512M) changes the cap the viewer starts under.
- **AC9** — A cap value that is not digits followed by K, M or G stops the launcher with a message naming the variable, and no viewer starts.
- **AC10** — On a machine with no systemd user session (macOS, WSL without a user bus), the viewer still starts, uncapped.
- **AC11** — If the memory scope cannot be started on a machine that should have one, the pane shows the error and no viewer starts uncapped.
- **AC12** — When the viewer is killed for passing its cap, the pane's terminal is left usable, one line says the viewer passed its cap, and the viewer restarts.
- **AC13** — When the viewer is killed for passing its cap shortly after it started, it does not restart in a loop: it waits for Enter before trying again, and stops if no input arrives.
- **AC14** — A viewer that exits with the same status without being capped is not restarted.
- **AC15** — lane-status prints one line per live viewer over the cap, naming the lane it belongs to (or its folder when no lane holds it), its size, the cap, its pane and its process id, and exits non-zero.
- **AC16** — lane-status prints nothing about viewers under the cap, and nothing about viewers whose process has exited or whose process id now belongs to another program.
- **AC17** — lane-status still names an oversized viewer when there are no open lanes.
- **AC18** — When lane-status cannot read the viewer list, it prints one line saying so with the reason, still prints every other line, and exits non-zero.
- **AC19** — A viewer line is reported once by lane-status's changes-only mode, not on every run while its size stays the same.
- **AC20** — Closing by lane name and closing by worktree path both close the one matching merged lane and remove its worktree.
- **AC21** — Closing a lane whose branch is not merged into the default branch refuses with a message saying so, and leaves the workspace, worktree and branch untouched.
- **AC22** — Closing a lane whose agent is still working refuses and leaves everything open.
- **AC23** — Closing the main checkout, a detached checkout, or a name or path that matches no open workspace refuses with a reason, and nothing changes.
- **AC24** — Closing by a name that matches several workspaces refuses and lists the candidates rather than closing one.
- **AC25** — Closing by name with no lane file entry under tuios refuses, because a name cannot be matched safely there.
- **AC26** — Closing a lane that does have a lane file entry, by name or by path, behaves as it did before.
- **AC27** — A merge that adds a script in the main, stowed checkout leaves the script linked in ~/.local/bin, for a fast-forward merge and for a merge commit.
- **AC28** — A merge in a linked worktree, or in a checkout that ~/.local/bin does not link to, restows nothing.
- **AC29** — When there is no gap in the script links, the merge runs no restow.
- **AC30** — When the restow fails (a real file is in the way) or stow is not installed, the merge still succeeds and a message names the failure.
- **AC31** — A shell that is not a Claude Code shell still gets the eza alias for ls.
- **AC32** — The CI workflow installs stow so the hook tests run there.

## Manual only

- **AC33** — A lane pane reopened on this branch runs hunk inside a systemd scope whose memory limit is 1G.
  Reason: needs a live herdr pane and the user's systemd session.
- **AC34** — `herdr-lane-resume --close no-such-lane-xyz` on the real machine exits 1 saying no lane has that name and closes nothing.
  Reason: reads the real lane file and herdr state.
