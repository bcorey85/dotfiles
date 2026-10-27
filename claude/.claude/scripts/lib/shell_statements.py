"""Read a shell command as statements of words, ignoring heredoc bodies, quoted strings and comments."""
import re

SKIP_WORDS = {"do", "then", "else", "elif", "if", "!", "time"}
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*\\?(['\"]?)([A-Za-z_][\w.-]*)\1")
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
COMMENT = re.compile(r"(^|\s)#[^\n]*")
COMMAND_SUBSTITUTION = re.compile(r"\$\(([^()]*)\)")
SEPARATORS = re.compile(r"\n|;|&&|\|\||\|&|\||&|\(|\)")


def strip_heredocs(command):
    kept = []
    delimiter = None
    for line in command.split("\n"):
        if delimiter is not None:
            if line.strip() == delimiter:
                delimiter = None
            continue
        kept.append(line)
        found = HEREDOC.search(line)
        if found:
            delimiter = found.group(2)
    return "\n".join(kept)


def clean(command):
    without_heredocs = strip_heredocs(command)
    without_quotes = QUOTED.sub('""', without_heredocs)
    without_comments = COMMENT.sub(r"\1", without_quotes)
    return COMMAND_SUBSTITUTION.sub(lambda match: "$<" + match.group(1).replace(" ", "\x00") + ">", without_comments)


def statements(command):
    # Each statement is a list of words. Leading do/then/else and env assignments are dropped.
    parsed = []
    for part in SEPARATORS.split(clean(command)):
        words = part.split()
        while words and (words[0] in SKIP_WORDS or re.match(r"^[A-Za-z_]\w*=", words[0])):
            words = words[1:]
        if words:
            parsed.append(words)
    return parsed
