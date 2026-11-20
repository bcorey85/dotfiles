~/.claude/scripts/review/verify-log review --result "NEEDS CHANGES" --rows - <<'JSON'
[{"desc":"omp bridge spawned .py gates with bare python3; an old python3 would deny every call","file":"omp/.omp/agent/hooks/pre/claude-security-bridge.ts","line":155,"class":"bug","actioned":"fixed"},
{"desc":"restore -sStable . read S/W inside a value as --staged/--worktree","file":"claude/.claude/scripts/lib/git_destructive_calls.py","line":94,"class":"bug","actioned":"fixed"},
{"desc":"clean -fdx -enode_modules read n inside -e value as dry run","file":"claude/.claude/scripts/lib/git_destructive_calls.py","line":73,"class":"bug","actioned":"fixed"},
{"desc":"env -C<dir> and sudo -D moved git without marking the call unplaced","file":"claude/.claude/scripts/lib/shell_command.py","line":937,"class":"bug","actioned":"fixed"},
{"desc":"calls cut from launcher text stayed placed","file":"claude/.claude/scripts/lib/git_calls.py","line":219,"class":"bug","actioned":"fixed"},
{"desc":"--git-dir naming a lane with no --work-tree passed from a main checkout","file":"claude/.claude/scripts/lib/git_calls.py","line":273,"class":"bug","actioned":"fixed"},
{"desc":"rule 7 read the hook process cwd, not the payload cwd","file":"claude/.claude/scripts/gates/git_discipline_gate.py","line":395,"class":"bug","actioned":"fixed"},
{"desc":"import guard installed a process-wide excepthook in tests that import a gate","file":"claude/.claude/scripts/lib/import_guard.py","line":1,"class":"bug","actioned":"fixed"},
{"desc":"corpus rows mislabeled redundant; no row for rule-7-only spellings","file":"tests/scripts/gate_replay_corpus.json","line":45,"class":"test","actioned":"fixed"},
{"desc":"bridge header misstated how the Python gates deny","file":"omp/.omp/agent/hooks/pre/claude-security-bridge.ts","line":22,"class":"docs","actioned":"fixed"},
{"desc":"lib module lists missed import_guard.py and git_destructive_calls.py","file":"docs/toolkit-script-rules.md","line":7,"class":"docs","actioned":"fixed"},
{"desc":"linked-worktree pass holds only for spellings bash-safety-gate misses; docs reworded to say so (ruling excluded CB-hook edits)","file":"claude/.claude/scripts/gates/git_discipline_gate.py","line":16,"class":"docs","actioned":"fixed"},
{"desc":"hand-rolled linked-worktree walk replaced by git rev-parse","file":"claude/.claude/scripts/lib/git_calls.py","line":230,"class":"smell","actioned":"fixed"},
{"desc":"script-file run with bare git commit argv words passed the commit gate","file":"claude/.claude/scripts/review/review_commit_gate.py","line":387,"class":"bug","actioned":"skipped_fp"},
{"desc":"nits: narrating test comment, str|None typing, rule-7 docstring missed core.hooksPath","file":"claude/.claude/scripts/lib/git_calls.py","line":1,"class":"nit","actioned":"fixed"}]
JSON
echo "exit=$?"; ~/.claude/scripts/review/verify-prep --ticket-file /tmp/claude-1000/-home-brandon-dotfiles-git-gates-destructive-and-crash/f1e7c4cf-2710-4486-b122-dc716efe7b9c/scratchpad/GITGATES-ticket.md 2>&1 | grep -E "STEP|FULL CHECK"
