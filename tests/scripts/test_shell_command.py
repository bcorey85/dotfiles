"""Checks for shell_command.py: reading a command line as steps joined by operators."""
import os
import pathlib
import sys
import unittest
import unittest.mock

import toolkit_paths

HERE = pathlib.Path(__file__).resolve().parent
LIVE_SCRIPTS_DIR = toolkit_paths.LIB_DIR
SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or (HERE if (HERE / "shell_command.py").exists()
                                                                  else LIVE_SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from shell_command import (
    and_steps,
    and_steps_or_whole,
    cd_folder,
    command_after_wrappers,
    contains_word_run,
    docker_forwarded_variables,
    docker_set_variables,
    is_git_word,
    names_code_runner,
    parse_simple_commands,
    path_word,
    quoted_positions,
    redirection_writes_file,
    runs_only_after_success,
    segment_words,
    shell_code_argument,
    split_command_steps,
    split_simple_commands,
    step_surely_ran,
    substitution_spans,
    unwrap_docker,
    without_assignments,
)


class IsGitWordTest(unittest.TestCase):
    def test_a_bare_git_or_a_path_to_git_counts_and_another_name_does_not(self):
        self.assertTrue(is_git_word("git"))
        self.assertTrue(is_git_word("/usr/bin/git"))
        self.assertFalse(is_git_word("git-lfs"))
        self.assertFalse(is_git_word("/usr/bin/gitk"))


class CdFolderTest(unittest.TestCase):
    def test_a_literal_folder_is_returned_and_a_bare_cd_goes_home(self):
        for words, folder in ((["cd", "sub"], "sub"), (["cd", "-P", "--", "sub"], "sub"), (["pushd", "sub"], "sub"),
                              (["cd"], "~"), (["cd", "~/sub"], "~/sub")):
            with self.subTest(words):
                self.assertEqual(folder, cd_folder(words))

    def test_a_folder_the_shell_resolves_gives_none(self):
        for words in (["popd"], ["pushd"], ["cd", "-"], ["cd", "a", "b"], ["cd", "$D"], ["cd", "sub*"],
                      ["cd", "~someone"], ["pushd", "+1"], ["pushd", "-1"], ["cd", "-1"], ["cd", "+2"]):
            with self.subTest(words):
                self.assertIsNone(cd_folder(words))


class AndStepsTest(unittest.TestCase):
    def test_a_command_joined_only_by_and_gives_its_stripped_steps(self):
        self.assertEqual(["ruff check .", "pytest -q"], and_steps("ruff check . && pytest -q"))

    def test_any_other_operator_gives_none(self):
        for command in ("a || b", "a | b", "a && b; c", "a & b"):
            with self.subTest(command):
                self.assertIsNone(and_steps(command))

    def test_any_other_operator_gives_the_stripped_command_as_the_one_step_when_asked_for_the_whole(self):
        self.assertEqual(["ruff check .", "pytest -q"], and_steps_or_whole(" ruff check . && pytest -q "))
        self.assertEqual(["a && b; c"], and_steps_or_whole(" a && b; c "))


class ContainsWordRunTest(unittest.TestCase):
    def test_the_run_must_stand_next_to_each_other_in_order(self):
        words = ["python3", "-m", "unittest", "tests.test_a"]
        cases = [(["-m", "unittest"], True), (["python3", "-m"], True), (["unittest", "-m"], False),
                 (["-m", "tests.test_a"], False), (["tests.test_a", "x"], False)]
        for run, expected in cases:
            with self.subTest(run=run):
                self.assertEqual(expected, contains_word_run(words, run))

    def test_words_shorter_than_the_run_hold_none(self):
        self.assertFalse(contains_word_run(["-m"], ["-m", "unittest"]))


class SplitSimpleCommandsTest(unittest.TestCase):
    def test_operators_and_groups_end_a_command_and_quotes_are_resolved(self):
        self.assertEqual(split_simple_commands('(cd x && git add "a b.md") ; git commit -m \'it is\' | cat & ls'),
                         [["cd", "x"], ["git", "add", "a b.md"], ["git", "commit", "-m", "it is"], ["cat"], ["ls"]])

    def test_an_unquoted_newline_ends_a_command_but_a_quoted_one_stays_in_the_word(self):
        self.assertEqual(split_simple_commands('git add a.md\ngit commit -m "one\ntwo"\n\n'),
                         [["git", "add", "a.md"], ["git", "commit", "-m", "one\ntwo"]])
        self.assertEqual(split_simple_commands("a &&\nb"), [["a"], ["b"]])

    def test_redirections_and_their_targets_are_dropped(self):
        self.assertEqual(split_simple_commands("git commit -m x 2>&1 >out.log"), [["git", "commit", "-m", "x"]])
        self.assertEqual(split_simple_commands("a &>/dev/null & b >> f"), [["a"], ["b"]])

    def test_a_hash_word_is_kept_not_read_as_a_comment(self):
        self.assertEqual(split_simple_commands("git add a.md # b"), [["git", "add", "a.md", "#", "b"]])

    def test_an_empty_quoted_word_is_a_word(self):
        self.assertEqual(split_simple_commands('git commit -m ""'), [["git", "commit", "-m", ""]])

    def test_text_it_cannot_trust_raises(self):
        for command in ('git commit -m "open', 'git commit -m ";"', "git commit -m '&&'", r"git add a\;b",
                        'a ";"', "a ;> b", 'a ">" b', "a '(' b", 'a "|" b', r"a \> b"):
            with self.assertRaises(ValueError, msg=command):
                split_simple_commands(command)

    def test_a_quoted_word_holding_only_a_newline_raises(self):
        for command in ('git commit -m y docs/x.md "\n" ls src/a.py', "a '\n' b", 'a "\n\n" b'):
            with self.assertRaises(ValueError, msg=command):
                split_simple_commands(command)

    def test_a_number_then_a_space_then_a_redirection_raises_but_a_file_descriptor_does_not(self):
        for command in ("git add a.md 5 >/dev/null", "a 5 > f", "a 12\t<in"):
            with self.assertRaises(ValueError, msg=command):
                split_simple_commands(command)
        self.assertEqual(split_simple_commands("a 2>&1 b 3>f"), [["a", "b"]])
        self.assertEqual(split_simple_commands("echo 5"), [["echo", "5"]])


class ParseSimpleCommandsTest(unittest.TestCase):
    def test_each_command_carries_its_redirections_with_their_targets(self):
        self.assertEqual(parse_simple_commands("echo x >> a.txt 2>&1 && git show HEAD:a > b <in &>c"),
                         [(["echo", "x"], [(">>", "a.txt"), (">&", "1")]),
                          (["git", "show", "HEAD:a"], [(">", "b"), ("<", "in"), ("&>", "c")])])

    def test_a_redirection_with_no_words_is_still_a_command_but_not_a_split_one(self):
        self.assertEqual(parse_simple_commands("echo x; > f"), [(["echo", "x"], []), ([], [(">", "f")])])
        self.assertEqual(split_simple_commands("echo x; > f"), [["echo", "x"]])

    def test_a_redirection_with_no_target_gets_an_empty_one(self):
        self.assertEqual(parse_simple_commands("a >"), [(["a"], [(">", "")])])
        self.assertEqual(parse_simple_commands("a > ; b"), [(["a"], [(">", "")]), (["b"], [])])
        self.assertEqual(parse_simple_commands("a > > f"), [(["a"], [(">", ""), (">", "f")])])

    def test_a_quoted_target_is_resolved_and_a_run_of_operator_characters_it_cannot_sort_raises(self):
        self.assertEqual(parse_simple_commands('a > "/dev/null"'), [(["a"], [(">", "/dev/null")])])
        with self.assertRaises(ValueError):
            parse_simple_commands("a <| f")

    def test_a_clobber_redirection_is_an_output_redirection(self):
        self.assertEqual(parse_simple_commands("echo x >| f.txt"), [(["echo", "x"], [(">|", "f.txt")])])
        self.assertTrue(redirection_writes_file(">|", "f.txt"))


class RedirectionWritesFileTest(unittest.TestCase):
    def test_an_output_redirection_to_a_file_writes(self):
        for operator in (">", ">>", "&>", "&>>", ">&", "<>"):
            self.assertTrue(redirection_writes_file(operator, ".husky/pre-commit"), operator)
        self.assertTrue(redirection_writes_file(">", ""))

    def test_dev_null_and_file_descriptor_copies_do_not_write(self):
        self.assertFalse(redirection_writes_file(">", "/dev/null"))
        self.assertFalse(redirection_writes_file("&>", "/dev/null"))
        for target in ("1", "2", "12", "-", "2-"):
            self.assertFalse(redirection_writes_file(">&", target), target)
        self.assertTrue(redirection_writes_file(">", "1"))

    def test_an_input_redirection_never_writes(self):
        for operator, target in (("<", ".git/index"), ("<<", "EOF"), ("<&", "0"), ("<<<", "text")):
            self.assertFalse(redirection_writes_file(operator, target), operator)


class SplitCommandStepsTest(unittest.TestCase):
    def test_each_step_carries_the_operator_before_it(self):
        steps = split_command_steps("a && b || c | d; e\nf")
        self.assertEqual(steps, [("", "a "), ("&&", " b "), ("||", " c "), ("|", " d"), (";", " e"), (";", "f")])

    def test_single_step_has_no_operator(self):
        self.assertEqual(split_command_steps("ls -la"), [("", "ls -la")])

    def test_a_lone_ampersand_is_an_operator(self):
        self.assertEqual(split_command_steps("a & b &"), [("", "a "), ("&", " b "), ("&", "")])

    def test_redirect_and_pipe_stderr_ampersands_stay_inside_their_step(self):
        for command in ("a 2>&1", "a >&2", "a &> f", "a &>> f", "a |& b"):
            self.assertEqual(len(split_command_steps(command)), 1, command)
        self.assertEqual(len(split_command_steps("a >f 2>&1 | b")), 2)

    def test_a_quoted_operator_stays_inside_its_step(self):
        steps = split_command_steps("rg -n 'typecheck|tsc|lint' f | head")
        self.assertEqual(steps, [("", "rg -n 'typecheck|tsc|lint' f "), ("|", " head")])
        for command in ('echo "a && b"', "echo 'a || b; c'", "echo a\\;b", 'echo "x\\" | y"'):
            self.assertEqual(len(split_command_steps(command)), 1, command)

    def test_an_unquoted_pipe_after_a_quoted_one_still_splits(self):
        self.assertEqual(len(split_command_steps("npm test | tee x")), 2)
        self.assertEqual(len(split_command_steps("echo 'a|b' && echo \"c;d\" ; ls")), 3)


class QuotedPositionsTest(unittest.TestCase):
    def test_an_unclosed_quote_covers_the_rest_unless_told_otherwise(self):
        command = "echo 'a | sh"
        pipe_index = command.index("|")
        self.assertIn(pipe_index, quoted_positions(command))
        self.assertNotIn(pipe_index, quoted_positions(command, unclosed_is_quoted=False))

    def test_a_closed_quote_covers_its_text_either_way(self):
        command = "echo 'a | b' | sh"
        inside = command.index("|")
        for unclosed_is_quoted in (True, False):
            positions = quoted_positions(command, unclosed_is_quoted=unclosed_is_quoted)
            self.assertIn(inside, positions)
            self.assertNotIn(command.rindex("|"), positions)

    def test_the_code_in_a_substitution_inside_double_quotes_is_not_quoted(self):
        for command in ('echo "a $(echo x > f) b"', 'echo "a `echo x > f` b"', 'echo "$(echo "q > r" > f)"'):
            positions = quoted_positions(command)
            self.assertNotIn(command.rindex(">"), positions, command)
            self.assertIn(command.index("b") if "q" not in command else command.index("q"), positions, command)

    def test_the_text_after_a_substitution_in_double_quotes_is_quoted_again(self):
        command = 'echo "$(true) | x" | y'
        positions = quoted_positions(command)
        self.assertIn(command.index("| x"), positions)
        self.assertNotIn(command.rindex("|"), positions)


class RunsOnlyAfterSuccessTest(unittest.TestCase):
    def test_steps_chained_by_and_run_only_after_the_earlier_step_succeeded(self):
        steps = split_command_steps("a && b && c")
        self.assertTrue(runs_only_after_success(steps, 0, 1))
        self.assertTrue(runs_only_after_success(steps, 0, 2))
        self.assertTrue(runs_only_after_success(steps, 1, 2))

    def test_semicolon_newline_or_and_pipe_let_the_later_step_run_after_a_failure(self):
        for command in ("a ; b", "a\nb", "a || b", "a | b"):
            steps = split_command_steps(command)
            self.assertFalse(runs_only_after_success(steps, 0, 1), command)

    def test_one_loose_operator_anywhere_between_the_steps_breaks_the_chain(self):
        steps = split_command_steps("a && b; c")
        self.assertTrue(runs_only_after_success(steps, 0, 1))
        self.assertFalse(runs_only_after_success(steps, 0, 2))
        self.assertFalse(runs_only_after_success(steps, 1, 2))

    def test_a_step_is_not_gated_by_itself_or_by_a_later_step(self):
        steps = split_command_steps("a && b && c")
        self.assertFalse(runs_only_after_success(steps, 1, 1))
        self.assertFalse(runs_only_after_success(steps, 2, 0))

    def test_pipes_after_the_first_and_keep_the_chain(self):
        steps = split_command_steps("a && b 2>&1 | tail && c | tail")
        self.assertEqual([runs_only_after_success(steps, 0, later) for later in (1, 2, 3, 4)], [True] * 4)

    def test_a_pipe_right_after_the_earlier_step_breaks_the_chain(self):
        steps = split_command_steps("a | cat && b")
        self.assertFalse(runs_only_after_success(steps, 0, 2))

    def test_a_group_entered_through_and_holds_the_chain_until_it_closes(self):
        steps = split_command_steps("a && { b; c; }; d")
        self.assertTrue(runs_only_after_success(steps, 0, 1))
        self.assertTrue(runs_only_after_success(steps, 0, 2))
        self.assertFalse(runs_only_after_success(steps, 0, 4))
        steps = split_command_steps("a && (b; c); d")
        self.assertTrue(runs_only_after_success(steps, 0, 2))
        self.assertFalse(runs_only_after_success(steps, 0, 3))

    def test_a_group_that_is_not_entered_through_and_gives_no_chain(self):
        steps = split_command_steps("a; { b; c; }")
        self.assertFalse(runs_only_after_success(steps, 0, 2))

    def test_an_or_before_the_earlier_step_can_skip_it(self):
        self.assertFalse(runs_only_after_success(split_command_steps("t || a && b"), 1, 2))
        self.assertFalse(runs_only_after_success(split_command_steps("x && t || a && b"), 2, 3))
        self.assertTrue(runs_only_after_success(split_command_steps("t || x; a && b"), 2, 3))
        self.assertTrue(runs_only_after_success(split_command_steps("t || x\na && b"), 2, 3))
        self.assertTrue(runs_only_after_success(split_command_steps("t & a && b"), 1, 2))

    def test_a_lone_ampersand_ends_the_chain(self):
        self.assertFalse(runs_only_after_success(split_command_steps("a & b"), 0, 1))
        self.assertFalse(runs_only_after_success(split_command_steps("a && b & c"), 0, 2))


class StepSurelyRanTest(unittest.TestCase):
    def test_after_success_only_or_hides_a_step(self):
        steps = split_command_steps("a && b || c")
        self.assertEqual([step_surely_ran(steps, i, True) for i in range(3)], [True, True, False])

    def test_after_failure_setup_steps_do_not_hide_the_next_step(self):
        steps = split_command_steps("cd x && source v && FOO=1 && export A=1 && pytest && eslint")
        self.assertEqual([step_surely_ran(steps, i, False) for i in range(6)],
                         [True, True, True, True, True, False])

    def test_after_failure_and_or_both_hide_a_step(self):
        steps = split_command_steps("a && b; c")
        self.assertEqual([step_surely_ran(steps, i, False) for i in range(3)], [True, False, False])

    def test_after_failure_semicolon_and_pipe_steps_ran(self):
        steps = split_command_steps("a; b | c")
        self.assertEqual([step_surely_ran(steps, i, False) for i in range(3)], [True, True, True])

    def test_a_step_sent_to_the_background_never_surely_ran(self):
        steps = split_command_steps("a & b")
        self.assertEqual([step_surely_ran(steps, i, True) for i in range(2)], [False, True])
        steps = split_command_steps("x; a && b | c &")
        self.assertEqual([step_surely_ran(steps, i, True) for i in range(4)], [True, False, False, False])


class UnwrapDockerTest(unittest.TestCase):
    def test_the_command_after_the_service_container_or_image_is_returned(self):
        cases = {
            "docker compose exec -T app pytest -q": ["pytest", "-q"],
            "docker-compose run --rm app npm test": ["npm", "test"],
            "docker exec -it web ls": ["ls"],
            "docker container run image echo hi": ["echo", "hi"],
            "docker run image": [],
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(expected, unwrap_docker(command.split()))

    def test_options_that_take_a_value_are_skipped_with_it_and_flags_are_not(self):
        words = ["docker", "compose", "-f", "ci.yml", "exec", "-e", "A=1", "--env", "B=2", "-w", "/app", "-u", "root",
                 "--workdir=/x", "-d", "app", "pytest"]

        self.assertEqual(["pytest"], unwrap_docker(words))

    def test_other_commands_are_not_docker_calls(self):
        for command in ("docker compose up -d", "docker ps", "docker build .", "pytest", ""):
            with self.subTest(command=command):
                self.assertIsNone(unwrap_docker(command.split()))
                self.assertEqual(set(), docker_forwarded_variables(command.split()))

    def test_variables_passed_by_name_are_forwarded_and_variables_given_a_value_are_not(self):
        cases = {
            "docker compose exec -e FILE app make test": {"FILE"},
            "docker compose run --rm --env FILE --env=OTHER -eMORE app make test": {"FILE", "OTHER", "MORE"},
            "docker exec -e FILE=x app make test": set(),
            "docker compose exec -w /app app make -e FILE": set(),
            "docker run --name FILE image make test": set(),
            "docker compose exec app make test": set(),
            "docker run -e": set(),
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(expected, docker_forwarded_variables(command.split()))

    def test_variables_given_a_value_are_set_and_variables_passed_by_name_are_not(self):
        cases = {
            "docker compose exec -e FILE=x app make test": {"FILE"},
            "docker compose run --rm --env FILE=x --env=OTHER=y -eMORE=z app make test": {"FILE", "OTHER", "MORE"},
            "docker exec -e FILE app make test": set(),
            "docker compose exec -w /app app make -e FILE=x": set(),
            "docker compose exec app make test": set(),
            "pytest -e FILE=x": set(),
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(expected, docker_set_variables(command.split()))

    def test_added_value_options_are_skipped_with_their_value(self):
        words = ["docker", "run", "--memory", "1g", "--cpus", "2", "--pull", "always", "--ulimit", "nofile=1", "app",
                 "pytest"]

        self.assertEqual(["pytest"], unwrap_docker(words))


class SubstitutionSpansTest(unittest.TestCase):
    def test_a_span_is_found_outside_quotes_and_inside_double_quotes(self):
        cases = {
            "echo $(a; b) x": ["a; b"],
            'echo "$(a > f)"': ["a > f"],
            "echo `a > f`": ["a > f"],
            'echo "`a`" $(b)': ["a", "b"],
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(expected, substitution_spans(command))

    def test_only_the_outermost_span_is_returned_with_its_inner_text_whole(self):
        self.assertEqual(["a $(b) c"], substitution_spans("echo $(a $(b) c)"))

    def test_a_span_in_single_quotes_a_comment_or_after_a_backslash_is_text(self):
        for command in ("echo '$(a)'", "echo x # $(a)", "echo \\$(a)", "echo '`a`'"):
            with self.subTest(command=command):
                self.assertEqual([], substitution_spans(command))

    def test_a_span_that_never_closes_runs_to_the_end(self):
        self.assertEqual(["a > f"], substitution_spans("echo $(a > f"))


class PathWordTest(unittest.TestCase):
    def test_quotes_at_the_ends_are_dropped_and_a_tilde_expands(self):
        with unittest.mock.patch.dict(os.environ, {"HOME": "/home/someone"}):
            self.assertEqual("/home/someone/f", path_word('"~/f"'))
            self.assertEqual("a.txt", path_word("'a.txt'"))


class WithoutAssignmentsTest(unittest.TestCase):
    def test_leading_assignments_are_dropped_and_later_ones_and_flags_stay(self):
        cases = {
            "A=1 B=2 pytest C=3": ["pytest", "C=3"],
            "pytest": ["pytest"],
            "A=1": [],
            "--env=x pytest": ["--env=x", "pytest"],
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(expected, without_assignments(command.split()))


class CommandAfterWrappersTest(unittest.TestCase):
    def test_wrapper_words_flags_and_values_are_peeled(self):
        cases = {
            "python3 -": ["python3", "-"],
            "env -i FOO=1 python3 -": ["python3", "-"],
            "env -u HOME python3 -": ["python3", "-"],
            "sudo -u root python3 -": ["python3", "-"],
            "sudo -E python3": ["python3"],
            "timeout 60 python3 -": ["python3", "-"],
            "timeout -s KILL 60 python3 -": ["python3", "-"],
            "nice python3": ["python3"],
            "nice -n 5 python3": ["python3"],
            "nohup python3": ["python3"],
            "command python3": ["python3"],
            "exec python3": ["python3"],
            "time python3": ["python3"],
            "uv run python -": ["python", "-"],
            "uv run --with rich python -": ["python", "-"],
            "poetry run python -": ["python", "-"],
            "pipenv run python -": ["python", "-"],
            "docker compose exec -T web python -": ["python", "-"],
            "sudo nice env FOO=1 timeout 5 python3": ["python3"],
            "stdbuf -oL tee f": ["tee", "f"],
            "stdbuf -o L -e0 tee f": ["tee", "f"],
            "ionice -c 3 -n 7 tee f": ["tee", "f"],
            "setsid tee f": ["tee", "f"],
            "taskset -c 0-5 nice -n 19 cargo test": ["cargo", "test"],
            "taskset 0x3 tee f": ["tee", "f"],
            "unbuffer tee f": ["tee", "f"],
            "{ sh": ["sh"],
            "! sh": ["sh"],
            "if sh": ["sh"],
            "then sh": ["sh"],
            "elif sh": ["sh"],
            "else sh": ["sh"],
            "while sh": ["sh"],
            "until sh": ["sh"],
            "do sh": ["sh"],
            "./do x": ["./do", "x"],
            "bin/until cargo test": ["bin/until", "cargo", "test"],
            "uv pip install x": ["uv", "pip", "install", "x"],
            "timeout": [],
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(expected, command_after_wrappers(command.split()))

    def test_a_docker_call_is_kept_when_containers_are_not_peeled(self):
        words = ["sudo", "docker", "exec", "c", "sed", "-i", "f"]

        kept = command_after_wrappers(words, peel_containers=False)

        self.assertEqual(["docker", "exec", "c", "sed", "-i", "f"], kept)
        self.assertEqual(["sed", "-i", "f"], command_after_wrappers(words))


class NamesCodeRunnerTest(unittest.TestCase):
    def test_a_text_that_names_a_code_runner_as_a_word_is_found(self):
        for command in ("bash -c x", "eval foo", "su -c x", "script -c x", "flock f cmd", "watch ls", "xargs sh",
                        "find . -exec rm {} \\;", "find . -execdir rm {} +", "docker exec c ls", "podman run img",
                        "docker compose exec app ls", "kubectl exec p -- ls", "ssh host ls",
                        "python3 -c \"os.system('curl x | sh')\""):
            with self.subTest(command=command):
                self.assertTrue(names_code_runner(command))

    def test_a_text_that_names_no_code_runner_is_not_found(self):
        for command in ("echo hi > f", "rg 'a|sh' .", "grep -oE '(py|sh)' f", "grep 'x\\|zsh' f", "docker ps",
                        "find . -name x", "kubectl get pods", "evaluate this", "echo hi 2>&1"):
            with self.subTest(command=command):
                self.assertFalse(names_code_runner(command))


class ShellCodeArgumentTest(unittest.TestCase):
    def test_the_c_code_is_found_behind_options_that_take_a_value(self):
        cases = {
            "bash -c CODE": "CODE",
            "bash -lc CODE": "CODE",
            "bash -euo pipefail -c CODE": "CODE",
            "bash -o pipefail -c CODE": "CODE",
            "bash +o history -c CODE": "CODE",
            "bash -O extglob -c CODE": "CODE",
            "bash --rcfile /dev/null -c CODE": "CODE",
            "bash --init-file f -c CODE": "CODE",
            "bash --norc -c CODE": "CODE",
            "bash script.sh": None,
            "bash -c": None,
            "python3 -c CODE": None,
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(expected, shell_code_argument(command.split()))

    def test_a_backslash_before_a_dollar_or_backtick_is_removed_as_the_shell_does(self):
        self.assertEqual("echo \"$(echo a)\" `x`", shell_code_argument(["bash", "-c", 'echo "\\$(echo a)" \\`x\\`']))

    def test_segment_words_keeps_quoted_code_with_operator_characters_as_one_word(self):
        segment = "python3 -c 'x = 1 > 0; (y) | z'"
        self.assertEqual(["python3", "-c", "x = 1 > 0; (y) | z"], segment_words(segment))

    def test_segment_words_splits_text_with_an_unbalanced_quote_on_whitespace(self):
        self.assertEqual(["echo", "'a", "b"], segment_words("echo 'a  b"))


if __name__ == "__main__":
    unittest.main()
