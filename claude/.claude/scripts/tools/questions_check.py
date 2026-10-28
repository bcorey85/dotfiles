"""Check a goal-blind research questions file (01-questions.md).

Usage: questions_check.py check <questions-file>

The question list runs from the `# ... Research Questions` heading to the next heading. Each question sits on one
line, numbered 1, 2, 3 ... in order, ends its question with `?`, and leaves no clause cut short before a `?`. Blank
lines are allowed between questions. Exit 0 when the file holds that shape; otherwise print each bad line with the
expected form and exit 1."""
import pathlib
import re
import sys

QUESTIONS_HEADING = re.compile(r"^# (?:.+ )?Research Questions\s*$")
QUESTION = re.compile(r"^(\d+)\. (\S.*)$")
# A `?` right after a conjunction, a comma or a space: a clause was deleted in place.
CUT_CLAUSE = re.compile(r"(?:\b(?:and|or|but|nor)|,)\s*\?|\s\?", re.I)
# A second numbered question after the first one's `?`: two questions merged onto one line.
MERGED_QUESTION = re.compile(r"\?\s*\d+\. ")


def question_lines(text):
    """(line number, line) for each line between the questions heading and the next heading; None without the
    heading."""
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if QUESTIONS_HEADING.match(line)), None)
    if start is None:
        return None

    section = []
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("#"):
            break
        section.append((index + 1, lines[index]))
    return section


def question_problems(text):
    """One `line N: ...` message per line that breaks the questions shape."""
    section = question_lines(text)
    if section is None:
        return ["no `# Research Questions` heading; expected the question list under it"]

    problems = []
    expected_number = 1
    for line_number, line in section:
        if not line.strip():
            continue
        question = QUESTION.match(line)
        if not question:
            problems.append(f"line {line_number}: expected `{expected_number}. <question>?` on one line, "
                            f"got: {line.strip()}")
            continue

        number, body = int(question.group(1)), question.group(2)
        if number != expected_number:
            problems.append(f"line {line_number}: question numbered {number}, expected {expected_number}")
        expected_number = number + 1
        if MERGED_QUESTION.search(body):
            problems.append(f"line {line_number}: two numbered questions on one line; put each on its own line")
        if CUT_CLAUSE.search(body):
            problems.append(f"line {line_number}: a clause ends cut short before `?`; rewrite the whole question")
        if "?" not in body:
            problems.append(f"line {line_number}: no `?`; expected each numbered line to ask a question")

    if expected_number == 1:
        problems.append("the question list is empty; expected `1. <question>?`")
    return problems


def main(argv):
    if len(argv) != 3 or argv[1] != "check":
        print(__doc__, file=sys.stderr)
        return 2

    path = pathlib.Path(argv[2])
    problems = question_problems(path.read_text())
    for problem in problems:
        print(f"{path}: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
