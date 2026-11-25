"""review_loop_ruling_check.py: the judgment of a fix pass against the rulings the run holds, as a mixin for `LoopRun`.
A ruling is free prose, so no grammar reads it: one `ruling-check` model call reads the pass diff against the ruling
texts. A pass the judge finds against a ruling has its work tree and index put back (byte for byte for the files
the backup holds) and the run stops. The put-back restores the work tree and index only: HEAD is not rewound, so a
commit the coder made during the pass stays in HEAD and the blocker names it. The host class holds repo,
out, files_touched, user_ruled, session_ruled, adopted, no_code_broken and user_only_paths, and has keep_open,
issue_text, coder_held_files, ruled_texts, keep_unreverted_open and drop_approval_asks."""
import functools
import pathlib
import sys
import types

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent / folder) for folder in (".", "../lib")]
import file_backup
import handback
import script_utils
from review_loop_calls import ModelCallError, claude_call
from review_loop_findings import ReplyShapeError, reply_with_one_retry

CHECK_FOLDER = "ruling-check"
BACKUP_FOLDER = "files"
DIFF_NAME = "pass.diff"
VERDICT_KEPT = "kept"
VERDICT_AGAINST = "against"
VERDICT_SHAPE = '{"verdicts": [{"ruling": "..", "verdict": "kept|against", "file": "..", "kept": ".."}]}'
USER_RULED_SOURCE = "user_ruled"
SESSION_RULED_SOURCE = "session_ruled"
ADOPTED_SOURCE = "adopted"
VERDICT_TEXT_KEYS = handback.ENTRY_TEXT_KEYS["against_ruling"]

# The notes for the packet's tool_fault: one for each ruling check that could not judge a pass.
RULING_CHECK_FAULTS = []


class RulingBrokenError(RuntimeError):
    """A fix pass that went against an accepted ruling. The message is the blocker."""


class RulingCheckFaultError(RuntimeError):
    """The ruling check could not judge a pass. The message is the blocker; the pass stays in the tree, or did not
    run when git could not list the repo files or read their index entries."""


def verdict_problem(parsed, ruling_count):
    """A sentence naming what is wrong with a judge reply's verdicts, None when they are fine. A reply with fewer
    verdicts than rulings judged some ruling not at all."""
    verdicts = parsed["verdicts"]
    if not isinstance(verdicts, list):
        return "'verdicts' must be a list"
    if len(verdicts) < ruling_count:
        return f"'verdicts' must hold one verdict for each of the {ruling_count} rulings, it holds {len(verdicts)}"
    for verdict in verdicts:
        if not isinstance(verdict, dict):
            return "each verdict must be an object"
        if verdict.get("verdict") not in (VERDICT_KEPT, VERDICT_AGAINST):
            return f"each verdict must be {VERDICT_KEPT!r} or {VERDICT_AGAINST!r}"
        if verdict["verdict"] != VERDICT_AGAINST:
            continue
        for key in VERDICT_TEXT_KEYS:
            value = verdict.get(key)
            if not isinstance(value, str) or not value.strip():
                return f"an {VERDICT_AGAINST!r} verdict needs a non-empty text for {key!r}"
    judged = {verdict["ruling"] for verdict in verdicts if isinstance(verdict.get("ruling"), str)}
    if len(judged) < ruling_count:
        return (f"'verdicts' must hold one verdict for each of the {ruling_count} rulings, "
                f"it names {len(judged)} different rulings")
    return None


def broken_blocker(call_name, verdict, commits, not_put_back):
    """The blocker line for one `against` verdict of the pass `call_name`. `commits` lists the commits the coder made
    during the pass; they stay in HEAD, because the put-back restores the work tree and index only and never rewinds
    HEAD. None means the loop could not read them. `not_put_back` is the set of
    paths the loop could not put back."""
    ending = "The pass was put back."
    if not_put_back:
        ending = "Part of the pass was put back."
    elif commits is None:
        ending = "The work tree and index were put back."
    elif commits:
        ending = "The work tree and index were put back; the coder's commit stays."
    return (f"fix pass {call_name} went against the accepted ruling on {verdict['file']}: "
            f"{verdict['ruling']}; it kept: {verdict['kept']}. {ending}")


class RulingCheck:
    # The {ruling, file, kept} of each ruling the last put-back pass went against. A tuple, replaced on each change.
    against_ruling = ()
    # The repo files that existed before the ruling-checked pass: a changed path outside it was created by the pass.
    ruling_files_before = frozenset()
    # The index entry of each backed-up path before the pass: the backup copies bytes only, so a `git add` of the pass
    # stays unless the entry is put back.
    ruling_index_entries = types.MappingProxyType({})
    # How many no-code broken entries, and which approval-ask paths, the run held before the ruling-checked pass.
    ruling_no_code_mark = 0
    ruling_ask_paths_before = frozenset()
    # The commit HEAD named before the ruling-checked pass, None in a repo with no commit.
    ruling_head_before = None

    def holds_ruling(self):
        """Whether the run holds an accepted ruling a fix pass is judged against."""
        return bool(self.ruled_texts or self.adopted)

    def begin_ruling_check(self, call_name, paths, findings, issue_texts):
        """The Backup of the files a pass may write and the existing files its findings name, left out the held files
        with a holder row (their owner may write them during the pass), or None when the run holds no ruling.
        Raises RulingCheckFaultError when git cannot list the repo files or read their index entries."""
        if not self.holds_ruling():
            return None

        listing = script_utils.repo_file_paths(self.repo)
        if listing is None:
            raise self.fault_before_pass(findings, f"tool fault: git could not list the files of {self.repo} so fix "
                                                   f"pass {call_name} did not run.")
        self.ruling_files_before = frozenset(listing)
        self.ruling_no_code_mark = len(self.no_code_broken)
        try:
            self.ruling_head_before = script_utils.head_commit_or_unborn(self.repo)
        except script_utils.GitCallError as error:
            raise self.fault_before_pass(
                findings, f"tool fault: {error} so fix pass {call_name} did not run.") from error
        self.ruling_ask_paths_before = frozenset(self.user_only_paths)
        named = [path for path in listing if script_utils.texts_name_path(issue_texts, path, self.repo)]
        backup_dir = self.out / CHECK_FOLDER / call_name / BACKUP_FOLDER
        backup = file_backup.save_files(self.repo, {*paths, *named} - self.coder_held_files(), backup_dir)
        try:
            # An absent path can still be a tracked entry whose file is deleted in the work tree.
            self.ruling_index_entries = script_utils.index_entries(
                self.repo, [*backup.saved, *backup.unsaved, *backup.absent])
        except script_utils.GitCallError as error:
            file_backup.discard(backup)
            raise self.fault_before_pass(
                findings, f"tool fault: {error} so fix pass {call_name} did not run.") from error
        return backup

    def fault_before_pass(self, findings, fault):
        """Keeps the findings open and records the tool fault; returns the error the caller raises."""
        self.keep_open(findings)
        RULING_CHECK_FAULTS.append(fault)
        return RulingCheckFaultError(fault)

    def discard_ruling_backup(self, backup):
        """Deletes the copies of a ruling check's backup; a None backup (no ruling held) has none."""
        if backup is not None:
            file_backup.discard(backup)

    def ruling_texts(self, findings):
        """[(source key, text)] of the accepted rulings the judge reads, each text once. A ruled finding of this pass
        shows as the coder got it, with its ruling mark. session_ruled holds both outcomes, so its tag says only
        where the text came from."""
        sources = [(USER_RULED_SOURCE, text) for text in self.user_ruled]
        sources += [(SESSION_RULED_SOURCE, text) for text in self.session_ruled]
        sources += [(ADOPTED_SOURCE, ruling.text) for ruling in self.adopted.values()]
        pass_texts = {finding.text: self.issue_text(finding) for finding in findings}
        shown = {}
        for source, text in sources:
            shown.setdefault(pass_texts.get(text, text), source)
        return [(source, text) for text, source in shown.items()]

    def ruling_check_prompt(self, call_name, findings, diff_file):
        lines = [f"You are the ruling-check judge for fix pass {call_name}.",
                 f"A [{USER_RULED_SOURCE}] or [{ADOPTED_SOURCE}] ruling below was accepted: the code it names "
                 f"must change as the ruling says. A [{SESSION_RULED_SOURCE}] text carries no outcome mark: judge it "
                 f"as accepted only when its text says so. Read the pass diff in {diff_file}, and the files "
                 f"it changes where the diff is not enough. Judge each ruling: "
                 f"'{VERDICT_AGAINST}' when the pass keeps what the ruling dropped or does what it forbade, "
                 f"'{VERDICT_KEPT}' otherwise. Name the file and what the pass kept for an '{VERDICT_AGAINST}'.",
                 "", "Rulings:"]
        lines += [f"- [{source}] {text}" for source, text in self.ruling_texts(findings)]
        lines += ["", f"End your reply with one JSON object: {VERDICT_SHAPE}."]
        return "\n".join(lines)

    def check_rulings_kept(self, call_name, findings, result, backup):
        """Judges a pass against the run's rulings. Returns at once with no backup or no changed file. A pass the
        judge finds against a ruling is put back and raises RulingBrokenError; one the judge cannot be reached for or
        read raises RulingCheckFaultError and stays in the tree. The put-back restores the work tree and index only;
        a coder commit made during the pass stays in HEAD."""
        if backup is None:
            return
        if not result.changed:
            return

        check_dir = self.out / CHECK_FOLDER / call_name
        diff_file = check_dir / DIFF_NAME
        check_dir.mkdir(parents=True, exist_ok=True)
        diff_file.write_text("\n\n".join(result.diffs))
        prompt = self.ruling_check_prompt(call_name, findings, diff_file)
        ruling_count = len(self.ruling_texts(findings))
        problem = functools.partial(verdict_problem, ruling_count=ruling_count)
        try:
            parsed = reply_with_one_retry(claude_call, "ruling-check", prompt, self.repo, self.out, ("verdicts",),
                                          VERDICT_SHAPE, problem=problem, model="sonnet", tools="Read,Grep")
        except (ReplyShapeError, ModelCallError) as error:
            fault = (f"tool fault: the ruling check of fix pass {call_name} could not run ({error}); the pass was "
                     f"not put back and its changes stay in the tree.")
            RULING_CHECK_FAULTS.append(fault)
            self.files_touched.update(result.changed)
            self.keep_unreverted_open(findings, result.reverted)
            raise RulingCheckFaultError(fault) from error

        against = [verdict for verdict in parsed["verdicts"] if verdict["verdict"] == VERDICT_AGAINST]
        if not against:
            return
        self.put_back_pass(call_name, findings, result, backup, against)

    def put_back_index_entries(self, created, backup):
        """Puts the index entry of each backed-up path the pass changed back to what it was, and takes each path the
        pass created out of the index. A path the backup could not save keeps its pass text, so its entry stays too.
        Returns the paths whose entry could not be read or restored."""
        saved_entries = {path: entry for path, entry in self.ruling_index_entries.items()
                         if path not in backup.unsaved}
        wanted_entries = {**dict.fromkeys(created), **saved_entries}
        return script_utils.restore_index_entries(self.repo, wanted_entries)

    def drop_pass_records_of(self, put_back):
        """Removes what the pass recorded: its no-code broken entries for the paths it restored, and the approval asks
        it filed for those restored paths. The wanted-change asks it filed stand."""
        kept_broken = list(self.no_code_broken[:self.ruling_no_code_mark])
        added_broken = self.no_code_broken[self.ruling_no_code_mark:]
        self.no_code_broken = kept_broken + [entry for entry in added_broken if entry["file"] not in put_back]
        filed_paths = [path for path in self.user_only_paths if path not in self.ruling_ask_paths_before]
        self.drop_approval_asks(filed_paths)

    def put_back_pass(self, call_name, findings, result, backup, against):
        """Restores every file the pass may have written, deletes the ones it created, keeps the findings open and
        raises RulingBrokenError naming each ruling the pass went against. A changed path the backup does not hold
        and the pass did not create, and a path whose index entry could not be restored, is named as not put back.
        A commit the coder made during the pass stays in HEAD and is named."""
        created = [path for path in result.changed if path not in self.ruling_files_before]
        put_back, left = file_backup.put_back_all(backup, created)
        self.drop_pass_records_of(set(put_back))
        self.keep_unreverted_open(findings, result.reverted)
        self.against_ruling = tuple({key: verdict[key] for key in VERDICT_TEXT_KEYS} for verdict in against)
        commits = script_utils.commits_since(self.repo, self.ruling_head_before)
        if commits is None or commits:
            # A restored path the coder's commit changed now differs from HEAD: the session commits the revert.
            # Unknown commits (None) count too: the pass may have committed.
            self.files_touched.update(put_back)
        covered = {*backup.saved, *backup.unsaved, *backup.absent, *created}
        changed_not_saved = [path for path in result.changed if path in backup.unsaved or path not in covered]
        not_put_back = {*changed_not_saved, *left, *self.put_back_index_entries(created, backup)}
        blockers = [broken_blocker(call_name, verdict, commits, not_put_back) for verdict in against]
        if commits is None:
            blockers.append("The loop could not tell whether the coder committed during the pass; check git log.")
        elif commits:
            blockers.append("Commits the coder made during the pass stay in HEAD: " + "; ".join(commits) + ".")
        if not_put_back:
            self.files_touched.update(not_put_back)
            not_put_back_names = ", ".join(sorted(not_put_back))
            blockers.append("Not put back, over the size cap, unreadable, outside the saved files, a directory "
                            "left in place or an index entry git could not restore: " + not_put_back_names + ".")
        raise RulingBrokenError(" ".join(blockers))
