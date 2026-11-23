"""Counts the words of the files a skill loads at start and fails when the total is above a limit.

Usage: python3 tests/scripts/skill_word_band.py <limit> <file> [<file> ...]

Prints `<words> <path>` for each file, then `<total> total (limit <limit>)`. A word is one item of
`str.split()`, except a bare list marker (`-`, `*`, `+` or `<digits>.`).
Exit 0 when the total is at or under the limit, 1 when it is above, 2 for a limit that is not an integer, a missing
file or no file named."""
import pathlib
import sys

EXIT_OVER_LIMIT = 1
EXIT_USAGE = 2


def usage_failure(message):
    print(f"skill_word_band: {message}", file=sys.stderr)
    return EXIT_USAGE


def is_list_marker(token):
    if token in ("-", "*", "+"):
        return True
    return token.endswith(".") and token[:-1].isdigit()


def count_words(text_file):
    tokens = text_file.read_text().split()
    return len([token for token in tokens if not is_list_marker(token)])


def main(argv):
    if len(argv) < 2:
        return usage_failure("usage: skill_word_band.py <limit> <file> [<file> ...]")

    limit_text = argv[0]
    try:
        limit = int(limit_text)
    except ValueError:
        return usage_failure(f"the limit {limit_text!r} is not an integer")

    files = [pathlib.Path(name) for name in argv[1:]]
    missing = [text_file for text_file in files if not text_file.is_file()]
    if missing:
        return usage_failure(f"no such file: {missing[0]}")

    total = 0
    for text_file in files:
        words = count_words(text_file)
        total += words
        print(f"{words} {text_file}")
    print(f"{total} total (limit {limit})")

    if total > limit:
        return EXIT_OVER_LIMIT
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
