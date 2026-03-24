---
name: stop-guessing
description: Circuit breaker — stop guessing, research the actual solution. Invoke when Claude has failed repeatedly to fix something by reasoning alone.
user-invocable: true
---

# Stop Guessing

The user has invoked this because you have been failing to fix something. Your current approach is not working.

## Rules

1. **STOP all current work immediately.** Do not attempt one more fix, do not try one more variation, do not "just check one thing."

2. **Acknowledge the failure.** In 1-2 sentences, state what you were trying to do and why it kept failing.

3. **Research.** Use WebSearch (multiple queries if needed) to find:
   - The exact error message + the tool/library versions involved
   - GitHub issues, Stack Overflow answers, or official docs that describe the problem
   - What other people actually did to fix it

4. **Summarize findings.** Present what you learned — not what you think, what the sources say.

5. **Propose a new plan** based on the research, not based on reasoning from first principles.

6. **Wait for user approval** before writing any code.

## What NOT to do

- Do NOT say "let me try one more thing" — that is the opposite of this skill's purpose
- Do NOT skip the WebSearch step
- Do NOT propose a fix based on reasoning alone — cite your source
- Do NOT resume the previous approach unless the research confirms it was correct
