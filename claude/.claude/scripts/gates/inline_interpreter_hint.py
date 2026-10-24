#!/usr/bin/env python3
"""PreToolUse hook on Bash: deny the inline interpreter runs that bash-safety-gate.sh blocks, with the way around.

The safety gate is generated and must not be edited, and its own block text names no other path, so agents retry
another inline form. This hook runs the gate's own interpreter-inline patterns through the system grep, as the gate
does, so it blocks what the gate blocks on each platform: macOS grep matches the rule across `|`, `;` and `&&` where
GNU grep stops at them. It denies with text that says what to do instead. Any error exits 0 with no output.
"""
import json
import os
import re
import subprocess
import sys

INLINE = r"\b(python3?|node|perl|ruby|php)\b[^;|&]*(\s-(c|e|r)\b|\s--?(eval|command)\b)"
ALLOWED = (r"import\s+(json|sys|os\.path|pathlib|re|math|hashlib|base64|urllib|collections|struct|platform|sysconfig|"
           r"ast|tomllib?|configparser|csv|io|textwrap|shutil|tempfile|glob|fnmatch|copy|pprint|inspect|importlib|"
           r"pkg_resources|packaging|setuptools|distutils)|JSON\.(parse|stringify)|require\(|"
           r"console\.(log|error|warn|dir)|process\.(version|arch|platform|cwd)|Buffer\.(from|alloc)")
INTERPRETER = re.compile(r"python|node|perl|ruby|php", re.I)
TEXT = ("Inline interpreter runs (python3 -c, node -e, perl -e, manage.py shell -c) are blocked. Do not retry another "
        "inline form. Write the code to a file in your scratchpad directory with the Write tool, then run the file: "
        "python3 <file>, node <file>, or python manage.py shell < <file>. If the command holds no inline code, run "
        "the interpreter step as its own Bash call, apart from any later -c, -e or -r flag.")


def grep(pattern, command):
    return subprocess.run(["grep", "-qiE", pattern], input=command + "\n", text=True).returncode == 0


def blocked(command):
    return bool(INTERPRETER.search(command)) and grep(INLINE, command) and not grep(ALLOWED, command)


def main():
    try:
        payload = json.loads(sys.stdin.read())
        command = (payload.get("tool_input") or {}).get("command")
        if not os.environ.get("CLAUDE_SKIP_HOOKS") and isinstance(command, str) and blocked(command):
            sys.stdout.write(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": TEXT}}))
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
