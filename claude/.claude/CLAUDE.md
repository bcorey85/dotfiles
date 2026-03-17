# Global Claude Code Rules

## Communication

- Never paste secrets — give me the command to run.
- Verify CLI syntax with `--help` before guessing.
- Be concise. Reference code with `file_path:line_number`.
- When a task spans >3 files or >1 service, propose a plan before writing code.

## Behavior

- Check for a project-level CLAUDE.md before starting work. It contains stack-specific commands and conventions.
- Don't over-engineer. Only change what's requested. Don't refactor unrelated code while implementing a feature.
- Never hardcode paths or project names in rules, agents, skills, or commands — keep portable.
- Don't guess at APIs, config options, or library interfaces. Use WebSearch to look it up, or check source/`--help` before writing code.
  If research would take >5 minutes, say so and ask for direction instead.
- Maximum 3 attempts on any failing approach. After 3, stop, document what failed, and ask for direction.
- After any code change, run the project's test/typecheck/lint commands before declaring done.
  If unknown, check the project CLAUDE.md or ask.
- Save all Playwright screenshots to `/tmp/`, never inside a project repo.
- Never include `#` comments inside Bash command strings. Put reasoning in prose before the tool call. Comments with quotes or apostrophes trigger the shell safety checker and spam permission prompts.

## Git

- Never commit directly to main/master. Work on a feature branch.
- Don't amend or force-push commits unless explicitly asked.
- Keep diffs focused — one logical change per task.

## Security

- NEVER SSH into remote servers (ssh, scp, rsync to remote hosts).
- NEVER read or cat credential/secret files.
- Use Ansible Vault for any secrets that need to be referenced.

## Obsidian

- Note vault: `~/vault`. Templates: `~/vault/Templates`.
- Suggest a note when a key insight or decision comes up.
