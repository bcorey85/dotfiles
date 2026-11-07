#!/usr/bin/env python3
"""Stop and SubagentStop hook: block a final message that says files are staged when the index does not hold them.
On Stop only, also block a main-session message that ends on a permission question for a reversible step
(permission_question.py), and send both reasons when both hold.

A sentence claims staging when it says `<is|are|were|was|now|all|been|left|remain|remains|stay|stays> staged`,
`I staged`, `I've staged` or `I have staged`, and holds no `not`, `no`, `nothing`, `none`, `never` or
`committed`, and no `if`, `whether`, `once`, `when`, `after`, `before`, `until` or `unless` ahead of the claim in its
own clause (clauses split at `,`, `;`, `:`, `and`, `but`, `so`), and no `row`, `record`, `diff` or `finding`
(or plural) as the word just before the claim, in a clause that names no `file`, unless the sentence also names
`index` or `git`: that is review data, not the index.

Three forms are not claims, judged on the clause up to the claim. A `stay` or `remain` claim whose clause already says
`staged` describes behavior ("files you staged stay staged"). A claim whose clause holds `say`, `said`, `claim` or
their inflections as a word of its own reports speech ("a reply that says files are staged"); the speech form does not
cover a speech verb that `I` or `we` come before. A claim whose clause names another session, agent, worker or peer,
or opens with a possessive peer, worker or coordinator ("the coordinator's files"), or with one as the whole
subject of `left staged`, reports that actor's work. None of these covers `I staged`,
`I've staged` or `I have staged`, which are judged by the review-data rule like any other claim.
Spans in double quotes (straight or curly) or backticks on one line are dropped only when they hold a whole claim.

The claim is checked against `git diff --cached --name-only` in the repo of each existing absolute or `~/` path the
sentence names and of each folder a `git -C <folder>` in it names (a relative folder read from the cwd), else in the
repo of the session cwd. It blocks when that index is empty, or when a file the sentence names, and that exists in the
repo, is not in it; a relative file is read from the cwd in a repo that holds the cwd, else from that repo's top. A
claim that names no such repo and no existing absolute path and finds the cwd index empty passes when a work tree
this session ran `git -C <tree> add` or `cd <tree> && ... git add` in, read from its transcript, holds staged files,
and every relative path the sentence names that exists in the cwd checkout or in that tree, resolved against that
tree, is among them: a session that stages that way keeps its cwd. A second stop in a row passes (stop_hook_active),
so a stuck session cannot spin. Fails open: any error exits 0 with no output.
"""
import contextlib
import functools
import json
import os
import re
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import permission_question
import script_utils
from git_calls import git_calls, joined_directory
from message_text import without_quoted_spans

STAGED_CLAIM = re.compile(r"\b(?:(?P<first_person>I(?:'ve| have)?\s+staged)"
                          r"|(?:is|are|were|was|now|all|been|(?P<left>left))\s+staged"
                          r"|(?P<lasting>remains?|stays?)\s+staged)\b", re.I)
NEGATION = re.compile(r"\b(?:not|no|nothing|none|never)\b", re.I)
COMMITTED = re.compile(r"\bcommitted\b", re.I)
CONDITIONAL = re.compile(r"\b(?:if|whether|once|when|after|before|until|unless)\b", re.I)
# Where one clause ends and the next begins, so a conditional in an earlier clause does not hide the claim.
CLAUSE_BREAK = re.compile(r"[,;:]|\s(?:and|but|so)\s", re.I)
# A claim whose subject is review data ("two rows are staged") speaks of a ledger or a diff folder, not the git index.
# The review noun must stand just before the claim, so "the diff of the file is staged" is still a claim.
REVIEW_DATA_SUBJECT = re.compile(r"\b(?:rows?|records?|diffs?|findings?)\s*$", re.I)
FILE_WORD = re.compile(r"\bfiles?\b", re.I)
GIT_INDEX = re.compile(r"\b(?:index|git)\b", re.I)
# The word on its own, not inside a hyphenated name or a path such as `docs/staged-claim.md`.
STAGED_WORD = re.compile(r"(?<![\w/-])staged(?![\w/-]|\.\w)", re.I)
# With no `another` or `other` ahead of it, a peer, coordinator or worker counts here only as a possessive that opens
# the clause ("the coordinator's files"), so "the fix to the worker" and "The worker is staged." stay claims.
OTHER_ACTOR = re.compile(r"\b(?:another|other)\s+(?:sessions?|agents?|workers?|peers?)\b"
                         r"|^\s*(?:(?:the|a)\s+)?(?:peers?|coordinator|workers?)"
                         r"(?:'|\N{RIGHT SINGLE QUOTATION MARK})(?:s\b|\s)", re.I)
# The same actor as the whole clause: it reports work only for `left staged` ("the worker left staged a list"),
# since "the worker is staged" says the actor itself is staged.
BARE_ACTOR = re.compile(r"^\s*(?:(?:the|a)\s+)?(?:peers?|coordinator|workers?)\s*$", re.I)
# A word on its own, so the name `staged-claim` is no report of speech.
REPORTED_SPEECH = re.compile(r"(?<![\w/-])(?:says?|said|saying|claims?|claimed|claiming)(?![\w/-])", re.I)
FIRST_PERSON = re.compile(r"\b(?:I|[Ww]e)\b")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
# A word that looks like a file path: `a.txt`, `docs/x.md`, `/abs/path`, `~/folder`.
PATH_WORD = re.compile(r"(?<![\w/.~-])(?:~/[\w-]+(?:[./][\w-]+)*|(?:/|\.{1,2}/)?[\w-]+(?:[./][\w-]+)+)")
# The folder a `git -C <folder>` call in the sentence runs in, without the quotes around it.
GIT_FOLDER = re.compile(r"\bgit\s+-C\s+['\"]?([^\s'\"`]+)")


@functools.cache
def session_staging_trees(transcript_path, cwd):
    """The work trees this session staged files in by naming the tree, as real paths. A relative tree is read from
    the session cwd."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return set()

    directories = set()
    for command in script_utils.bash_commands(transcript_path):
        directories |= {call.directory for call in git_calls(command, cwd) if call.subcommand == "add"}

    trees = set()
    for directory in directories:
        top = script_utils.work_tree_top(directory) if os.path.isdir(directory) else None
        if top:
            trees.add(top)
    return trees


def claim_sentences(message):
    claims = []
    unquoted_message = without_quoted_spans(STAGED_CLAIM, message)
    for sentence in SENTENCE_END.split(unquoted_message):
        if NEGATION.search(sentence) or COMMITTED.search(sentence):
            continue
        if any(is_index_claim(sentence, claim) for claim in STAGED_CLAIM.finditer(sentence)):
            claims.append(sentence)
    return claims


def is_index_claim(sentence, claim):
    """Whether one staged-claim match speaks of the git index, judged by the clause just before it."""
    clauses = CLAUSE_BREAK.split(sentence[:claim.start()])
    clause = clauses[-1]
    if CONDITIONAL.search(clause):
        return False
    if not claim.group("first_person"):
        reports_other_actor = OTHER_ACTOR.search(clause) or (claim.group("left") and BARE_ACTOR.search(clause))
        if reports_other_actor:
            return False
        if claim.group("lasting") and STAGED_WORD.search(clause):
            return False
        speech = REPORTED_SPEECH.search(clause)
        if speech and not FIRST_PERSON.search(clause[:speech.start()]):
            return False

    names_review_data = REVIEW_DATA_SUBJECT.search(clause) and not FILE_WORD.search(clause)
    return not names_review_data or bool(GIT_INDEX.search(sentence))


def path_words(sentence):
    """The path words of a sentence, with a leading `~` expanded."""
    return [os.path.expanduser(word) for word in PATH_WORD.findall(sentence)]


def named_absolute_paths(sentence):
    """The existing absolute paths a sentence names, as real paths."""
    absolute = [word for word in path_words(sentence) if word.startswith("/")]
    return [os.path.realpath(word) for word in absolute if os.path.exists(word)]


def named_trees(sentence, cwd):
    """The work trees a sentence names, as real paths: the tree of each existing absolute path, and of each folder a
    `git -C <folder>` call runs in, a relative folder read from the cwd."""
    joined_folders = [joined_directory(cwd, folder) for folder in GIT_FOLDER.findall(sentence)]
    git_folders = [folder for folder in joined_folders if folder != cwd]
    existing_folders = [os.path.realpath(folder) for folder in git_folders if os.path.isdir(folder)]
    paths = named_absolute_paths(sentence) + existing_folders
    return {top for top in map(script_utils.work_tree_top, paths) if top}


def named_files(sentence, base):
    """The existing files a sentence names, as real absolute paths. A relative path is read from base."""
    files = []
    for word in path_words(sentence):
        path = os.path.join(base, word)
        if os.path.isfile(path):
            files.append(os.path.realpath(path))
    return files


def session_tree_holds(top, sentence, cwd, transcript_path):
    """Whether a work tree other than top, one the session staged in, has every relative path the sentence names in
    its index. A path counts when it exists in the cwd checkout or in that tree."""
    offset = os.path.relpath(os.path.realpath(cwd), top)
    words = [word for word in path_words(sentence) if not word.startswith("/")]
    for tree in session_staging_trees(transcript_path, cwd) - {top}:
        staged_output = script_utils.git_output(tree, "diff", "--cached", "--name-only")
        tree_base = os.path.join(tree, offset)
        required = {os.path.normpath(os.path.join(offset, word)) for word in words
                    if os.path.isfile(os.path.join(cwd, word)) or os.path.isfile(os.path.join(tree_base, word))}
        if staged_output and required <= set(staged_output.splitlines()):
            return True
    return False


def sentence_problems(sentence, cwd, transcript_path):
    """What the index of each repo the sentence speaks of lacks, one line per repo. A relative path is read from the
    cwd in a repo that holds the cwd, else from that repo's top."""
    named_tops = named_trees(sentence, cwd)
    tops = named_tops or {script_utils.work_tree_top(cwd)} - {None}
    names_a_place = bool(named_tops or named_absolute_paths(sentence))
    real_cwd = os.path.realpath(cwd)

    problems = []
    for top in sorted(tops):
        staged_output = script_utils.git_output(top, "diff", "--cached", "--name-only")
        if staged_output is None:
            continue

        staged = staged_output.splitlines()
        base = real_cwd if script_utils.path_is_under(real_cwd, top) else top
        named = [os.path.relpath(path, top) for path in named_files(sentence, base)
                 if script_utils.path_is_under(path, top)]
        if not staged and not names_a_place and session_tree_holds(top, sentence, cwd, transcript_path):
            continue
        if not staged:
            problems.append(f"the index of {top} holds nothing")
            continue

        missing = [path for path in named if path not in staged]
        if missing:
            problems.append(f"the index of {top} does not hold {', '.join(missing)}")
    return problems


def staged_claim_reason(hook, message):
    """The block reason for a staged claim the index does not back, or None."""
    claims = claim_sentences(message)
    if not claims:
        return None

    cwd = hook.get("cwd") or os.getcwd()
    transcript_path = hook.get("transcript_path")
    problems = [problem for sentence in claims for problem in sentence_problems(sentence, cwd, transcript_path)]
    if not problems:
        return None
    return (f"Your message says files are staged, but {'; '.join(dict.fromkeys(problems))}. Run "
            "`git diff --cached --name-only` in that repo and say what the index holds.")


def main():
    hook = json.load(sys.stdin)
    if hook.get("stop_hook_active"):
        return
    message = hook.get("last_assistant_message") or ""

    reasons = [staged_claim_reason(hook, message)]
    is_main_session = hook.get("hook_event_name") == "Stop"
    if is_main_session and permission_question.closing_question(message):
        reasons.append(permission_question.REASON)

    found_reasons = [reason for reason in reasons if reason]
    if found_reasons:
        print(json.dumps({"decision": "block", "reason": " ".join(found_reasons)}))


if __name__ == "__main__":
    if not os.environ.get("CLAUDE_SKIP_HOOKS"):
        with contextlib.suppress(Exception):
            main()
