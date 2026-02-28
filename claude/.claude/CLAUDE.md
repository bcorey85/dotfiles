## Communication

- Never paste secrets — give me the command to run.
- Verify CLI syntax with `--help` before guessing.
- Be concise. Reference code with `file_path:line_number`.

## Behavior

- Don't over-engineer. Only change what's requested.
- Never hardcode paths or project names in rules, agents, skills, or commands — keep portable.
- Only add rules that increase efficiency or reduce rework. Don't duplicate the system prompt.
- Always prefer multiple parallel subagents when appropriate. Speed > token efficiency.

## Obsidian

Note vault: `~/vault`. Templates: `~/vault/Templates`.
Suggest a note when a key insight or decision comes up.

# Global Claude Code Rules

## Security

- NEVER SSH into remote servers (ssh, scp, rsync to remote hosts)
- NEVER read or cat credential/secret files
- Use Ansible Vault for any secrets that need to be referenced
