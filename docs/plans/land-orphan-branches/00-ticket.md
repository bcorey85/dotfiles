# Land orphan branches

Four finished lane branches whose orchestrator is gone, landed onto fix/land-orphan-branches. Criteria are each
queue item's Done when, verbatim.

## Acceptance Criteria

- AC1 (herdr-restore): Read herdr's restore path and confirm which command it runs. If the variable is lost, a test shows a restored lane starts with cron off. Prefer a fix in the herdr launch command over writing a settings file into each worktree.

- AC2 (settings-hook): A toolkit script adds or removes one hook entry (event, matcher, command) in settings.json idempotently, keeps the file's format byte-identical apart from the entry, and prints what it changed.
- AC3: Lanes and orchestration hand that script's one line for every settings.json hook change.
- AC4: Tests: adding twice writes once; a round trip leaves other entries untouched.

- AC5 (cc): cc/SKILL.md carries disable-model-invocation: true and a short description.
- AC6: A headless run with the live config shows cc absent from the init event's model-invocable skills, and /cc still runs.
- AC7: A change file and a rule-anchors row update land with it.

- AC8 (pyright): A pyrightconfig.json at the dotfiles root lists the claude/.claude/scripts subfolders as extraPaths, and an open .claude script in the editor's pyright gets no unresolved toolkit import, and the same extraPaths in an absolute-path config outside a dot-folder shows no unresolved import while a missing one still shows.

## Decision log

- 2026-11-24, agent-evals-6b (session; criteria owner session): AC6 cannot pass before the branch lands, since the live config is master. It is met before landing by the headless probe with the edited skill as a project skill (flag hides it from the model, /cc stays in the slash commands). The live-config check runs after the landing line, before the item closes.
- 2026-11-27, agent-evals-c3-owner (session; criteria owner session): AC3's orchestration half is met by the lane-brief line alone; no orchestration.md bullet. LB02 measures the lane line at 6/6 on, 0/6 off.
- 2026-11-27, fix/land-orphan-branches lane: the tools/settings_hook.py owner line in claude/.claude/scripts/CLAUDE.md is dropped, per the user's earlier ruling against new Owners lines in that file; the line goes back only on the user's yes.
- 2026-11-27, agent-evals-c3-owner (session; criteria owner session): AC8 reworded from the CLI check on the two named files to the editor and absolute-path-config check, since the pyright CLI skips dot-folders by default and the defect was editor diagnostics.
