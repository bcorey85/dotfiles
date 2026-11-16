"""Checks for shell_variables.py (the proven values of a command's variables)."""
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))

from shell_variables import ShellVariables


def values(command, target, step=None):
    variables = ShellVariables(command)
    index = len(variables.steps) - 1 if step is None else step
    return variables.literal_values(target, index)


class LiteralValuesTest(unittest.TestCase):
    def test_a_bare_assignment_before_the_use_gives_its_value(self):
        for command in ("S=/tmp/x; echo hi > $S/a", "export S=/tmp/x; echo hi > $S/a", "S=/tmp/x && echo hi > $S/a",
                        "S=/tmp/x\necho hi > $S/a", 'S="/tmp/x"; echo hi > $S/a', "S='/tmp/x'; echo hi > $S/a"):
            self.assertEqual(values(command, "$S/a"), ["/tmp/x/a"], command)

    def test_a_name_set_inside_a_subscript_or_a_nameref_value_is_unproven(self):
        for hiding in ("a[S=1]=y", "a[S=3]+=1", "a[S++]=1", "declare -n R='S[0]'", "local -n R='S[0]'",
                       "echo $a[S-=2]"):
            self.assertIsNone(values(f"S=/tmp/x; {hiding}; echo hi > $S/a", "$S/a"), hiding)

    def test_an_integer_literal_subscript_stays_readable(self):
        self.assertEqual(values("S=/tmp/x; a[0]=y; echo hi > $S/a", "$S/a"), ["/tmp/x/a"])

    def test_a_quoted_assignment_keeps_its_value_and_a_bare_empty_one_stays_empty(self):
        self.assertEqual(values('S="/tmp/swg"; echo hi > "$S/a.log"', '"$S/a.log"'), ['"/tmp/swg/a.log"'])
        self.assertEqual(values("S=; echo hi > $S/a", "$S/a"), ["/a"])

    def test_a_non_ascii_name_is_unproven(self):
        self.assertIsNone(values("é=/tmp/x; echo hi > $é/a", "$é/a"))
        self.assertIsNone(values("for é in a b; do echo hi > /tmp/$é/a; done", "/tmp/$é/a", step=1))

    def test_a_name_the_shell_overrides_is_unproven(self):
        for name in ("MATCH", "BASH_REMATCH", "DIRSTACK", "USERNAME", "FUNCNAME", "_", "pipestatus",
                     "SHELLOPTS", "BASHOPTS", "BASH_VERSINFO", "BASH_MONOSECONDS"):
            self.assertIsNone(values(f"{name}=/tmp/x; echo hi > ${name}/a", f"${name}/a"), name)

    def test_a_named_descriptor_or_an_ifs_use_leaves_the_name_unproven(self):
        for command in ("S=/tmp/x; : {S}>/tmp/q; echo hi > $S/a", "S=/tmp/x; IFS=/; echo hi | tee $S"):
            self.assertIsNone(values(command, "$S/a"), command)

    def test_several_names_join_in_order(self):
        self.assertEqual(values("S=/tmp/x; N=a; echo hi > ${S}/$N.log", "${S}/$N.log"), ["/tmp/x/a.log"])

    def test_a_loop_over_literal_words_gives_every_word_inside_its_body(self):
        command = "for d in a b; do echo hi > /tmp/$d/x; done"
        self.assertEqual(values(command, "/tmp/$d/x", step=1), ["/tmp/a/x", "/tmp/b/x"])

    def test_the_loop_name_outside_its_body_is_unproven(self):
        self.assertIsNone(values("for d in a b; do echo; done; echo hi > /tmp/$d/x", "/tmp/$d/x"))

    def test_unproven_values_give_none(self):
        for command in ("echo hi > $S/a", "S=/tmp/x; S=/etc; echo hi > $S/a", "S=$(pwd); echo hi > $S/a",
                        "S=/tmp/*; echo hi > $S/a", "S=~; echo hi > $S/a", "S=/tmp/x & echo hi > $S/a",
                        "S=/tmp/x | cat; echo hi > $S/a", "S=/tmp/x/..; echo hi > $S/a",
                        "(S=/tmp/x); echo hi > $S/a", "if true; then S=/tmp/x; fi; echo hi > $S/a",
                        "read S; echo hi > $S/a", "eval S=/etc; S=/tmp/x; echo hi > $S/a",
                        "S=/tmp/x; echo '$S' > $S/a", "S=/tmp/x; echo hi > $S/a$((1+1))",
                        "S=/tmp/x; echo hi > $S/$1", "S=/tmp/x; echo hi > `echo $S`"):
            self.assertIsNone(values(command, command.rsplit("> ", 1)[-1]), command)

    def test_a_target_with_expansion_syntax_is_unproven(self):
        for target in ("$S[1]/zz", "${S}[1]/zz", "$S:h:h/zz", "${S}:h/zz", "$S/*", "$S/?", "$S/{a,b}", "$S/\\zz",
                       "~/$S", "${S:-x}/a", "${S}x}/a", "$S/passwd(:s.tmp.etc.)", "$S/a(:h:h:h)", "$S/a<->",
                       "$S/a#b", "$S/a^b", "=ls$S", "$S/a|b", '"=ls$S"', '"$S"/a'):
            self.assertIsNone(values(f"S=/tmp/x; echo hi > {target}", target), target)

    def test_a_target_of_safe_characters_around_one_pair_of_quotes_is_proven(self):
        self.assertEqual(values("S=/tmp/x; echo hi > $S/a-b_c.log", "$S/a-b_c.log"), ["/tmp/x/a-b_c.log"])
        self.assertEqual(values('S=/tmp/x; echo hi > "$S/a"', '"$S/a"'), ['"/tmp/x/a"'])

    def test_a_same_name_inner_loop_that_already_ended_is_unproven(self):
        command = "for t in /tmp/claude-1000; do for t in /home/brandon; do :; done; echo > $t/x; done"
        self.assertIsNone(values(command, "$t/x", step=4))

    def test_a_subscript_assignment_counts_as_a_second_assignment(self):
        for command in ("S=/tmp/claude-1000; S[1,16]=/home/brandon/zz; echo > $S/a",
                        "S=/tmp/claude-1000; S[1]+=/home/brandon/zz; echo > $S/a"):
            self.assertIsNone(values(command, "$S/a"), command)

    def test_a_builtin_that_sets_a_name_without_an_equals_sign_makes_the_name_unproven(self):
        for builtin in ("print -v S /etc", "integer S", "vared S", "sysread S", "read S", "read -r S < f", "unset S",
                        "declare S", "typeset -n R S", "printf -v S x", "getopts ab S", "mapfile S < f",
                        "read 'S?prompt'", "read \"S\"", "export S"):
            command = f"S=/tmp/x; {builtin}; echo hi > $S/a"
            self.assertIsNone(values(command, "$S/a"), command)
        self.assertIsNone(values("echo | while read S; do echo hi > $S/a; done", "$S/a", step=2))

    def test_a_builtin_that_sets_a_name_it_never_writes_makes_that_name_unproven(self):
        for command in ("REPLY=/tmp/x; read; echo hi > $REPLY/a", "OPTARG=/tmp/x; getopts ab o; echo hi > $OPTARG/a",
                        "PWD=/tmp/x; cd /etc; echo hi > $PWD/a", "MAPFILE=/tmp/x; mapfile < f; echo hi > $MAPFILE/a",
                        "S=/tmp/x; let S++; echo hi > $S/a"):
            self.assertIsNone(values(command, command.rsplit("> ", 1)[-1]), command)

    def test_a_name_the_shell_sets_itself_is_unproven(self):
        for name in ("RANDOM", "SECONDS", "LINENO", "UID", "EUID", "PPID", "BASHPID", "SRANDOM", "EPOCHSECONDS",
                     "EPOCHREALTIME", "HISTCMD", "BASH_COMMAND", "GROUPS", "SHLVL", "PWD", "REPLY"):
            command = f"{name}=/tmp/x; echo hi > ${name}/a"
            self.assertIsNone(values(command, f"${name}/a"), command)

    def test_a_dot_or_source_command_after_a_keyword_or_wrapper_leaves_names_unproven(self):
        for sourcing in ("if true; then . ./env.sh; fi", "command . ./env.sh", "builtin . ./env.sh",
                         "while false; do source ./env.sh; done", "builtin eval 'S=/etc'", "command source ./e.sh",
                         "time . ./env.sh", "then . ./env.sh"):
            command = f"S=/tmp/x; {sourcing}; echo hi > $S/a"
            self.assertIsNone(values(command, "$S/a"), command)

    def test_a_dot_command_behind_a_zsh_precommand_modifier_leaves_names_unproven(self):
        for sourcing in ("nocorrect . ./env.sh", "noglob . ./env.sh", "- . ./env.sh",
                         "nocorrect noglob command builtin . ./env.sh"):
            command = f"S=/tmp/x; {sourcing}; echo hi > $S/a"
            self.assertIsNone(values(command, "$S/a"), command)

    def test_a_command_that_aliases_or_changes_how_a_value_expands_leaves_names_unproven(self):
        for changing in ("alias s=.", "command alias s=.", "if true; then alias s=.; fi", "setopt shwordsplit",
                         "unsetopt glob", "emulate sh", "nocorrect setopt kshglob", "builtin emulate -L sh"):
            command = f"S=/tmp/x; {changing}; echo hi > $S/a"
            self.assertIsNone(values(command, "$S/a"), command)

    def test_a_set_option_change_keeps_the_proof(self):
        self.assertEqual(values("S=/tmp/x; set -o pipefail; echo hi > $S/a", "$S/a"), ["/tmp/x/a"])

    def test_a_loop_name_is_assigned_even_when_the_command_is_unreadable(self):
        variables = ShellVariables("for TMPDIR in /home/x; do echo x > $TMPDIR/n; done; let n=1")
        self.assertIn("TMPDIR", variables.assigned_names)
        variables = ShellVariables("for HOME in /home/x; do :; done; eval y")
        self.assertIn("HOME", variables.assigned_names)

    def test_a_loop_word_named_like_a_builtin_is_no_unreadable_command(self):
        command = "for t in read write declare; do echo hi > /tmp/x_$t.log; done"
        self.assertEqual(values(command, "/tmp/x_$t.log", step=1),
                         ["/tmp/x_read.log", "/tmp/x_write.log", "/tmp/x_declare.log"])

    def test_a_colon_in_a_value_or_after_plain_text_is_allowed(self):
        self.assertEqual(values("S=/tmp/x:y; echo hi > $S/a", "$S/a"), ["/tmp/x:y/a"])
        self.assertEqual(values("S=/tmp/x; echo hi > $S/a:b", "$S/a:b"), ["/tmp/x/a:b"])

    def test_a_name_assigned_after_the_use_is_unproven(self):
        self.assertIsNone(values("echo hi > $S/a; S=/tmp/x", "$S/a", step=0))

    def test_a_chain_that_may_skip_the_assignment_is_unproven(self):
        self.assertIsNone(values("false || S=/tmp/x; echo hi > $S/a", "$S/a"))

    def test_too_many_combinations_are_unproven(self):
        words = " ".join(str(number) for number in range(9))
        command = f"for a in {words}; do for b in {words}; do echo hi > /tmp/$a/$b; done; done"
        self.assertIsNone(values(command, "/tmp/$a/$b", step=2))
        small = "for a in 1 2; do for b in 1 2; do echo hi > /tmp/$a/$b; done; done"
        self.assertEqual(len(values(small, "/tmp/$a/$b", step=2)), 4)

    def test_a_builtin_that_names_the_variable_by_escape_or_expansion_makes_it_unproven(self):
        for builtin in ("printf -v \\S %s /home/brandon", "read -r \\S < /tmp/claude-1000/f",
                        "printf -v S$E %s /home/brandon", 'N=T; printf -v "${N/T/S}" %s /home/brandon',
                        "read \\S <<< /home/brandon", "printf -v \\S /home/brandon", "unset \\S",
                        "declare S\\=/home/brandon/newdir", "export S\\=/home/brandon",
                        "P=Q; printf -v \"${P/Q/S}\" /home/brandon"):
            command = f"S=/tmp/claude-1000/x; {builtin}; echo hi > $S/a"
            self.assertIsNone(values(command, "$S/a"), command)

    def test_a_name_attached_to_an_option_cluster_is_unproven(self):
        for builtin in ("printf -vS %s /home/brandon", "read -aS <<< /home/brandon", "print -vS /home/brandon",
                        "read -raS <<< /home/brandon", "wait -pS", "mapfile -tS", "zparseopts -AS"):
            command = f"S=/tmp/claude-1000/x; {builtin}; echo hi > $S/a"
            self.assertIsNone(values(command, "$S/a"), command)

    def test_a_computed_name_word_after_a_redirect_is_unproven(self):
        for builtin in ("read <<< /home/brandon $(cat /tmp/claude-1000/n)",
                        "printf >/dev/null -v $(cat /tmp/claude-1000/n) %s /home/brandon",
                        "read <<< /home/brandon `cat /tmp/claude-1000/n`",
                        "read <<< /home/brandon $(tr a-z A-Z <<< s)", "printf -v S`x` %s /home/brandon"):
            command = f"S=/tmp/claude-1000/x; {builtin}; echo hi > $S/a"
            self.assertIsNone(values(command, "$S/a"), command)

    def test_a_redirect_word_before_or_inside_a_name_setting_builtin_does_not_hide_a_computed_name(self):
        for builtin in (">/dev/null printf -v $(cat /tmp/claude-1000/n) %s x",
                        "2>/dev/null read $(cat /tmp/claude-1000/n)",
                        "&>/dev/null read $(cat /tmp/claude-1000/n)",
                        "printf -v >/dev/null $(cat /tmp/claude-1000/n) %s x"):
            command = f"S=/tmp/claude-1000/x; {builtin}; echo hi > $S/a"
            self.assertIsNone(values(command, "$S/a"), command)

    def test_set_with_the_array_option_and_a_computed_name_is_unproven(self):
        for builtin in ("set -A $(cat /tmp/claude-1000/n) x", "set -A `cat /tmp/claude-1000/n` x",
                        "set -eA $(cat /tmp/claude-1000/n) x"):
            command = f"S=/tmp/claude-1000/x; {builtin}; echo hi > $S/a"
            self.assertIsNone(values(command, "$S/a"), command)
        plain = "S=/tmp/claude-1000/x; set -o pipefail; set -A arr x y; echo hi > $S/a"
        self.assertEqual(values(plain, "$S/a"), ["/tmp/claude-1000/x/a"])

    def test_a_non_numeric_operand_of_an_arithmetic_test_is_unproven(self):
        for evaluation in ("E=$(cat /tmp/claude-1000/f); [[ E -eq 1 ]]", "read E < /tmp/claude-1000/f; [[ $E -lt 1 ]]",
                           "E=$(cat /tmp/claude-1000/f); echo $[E]"):
            command = f"S=/tmp/claude-1000/x; {evaluation}; echo hi > $S/a"
            self.assertIsNone(values(command, "$S/a"), command)
        numeric = "S=/tmp/claude-1000/x; [[ 3 -eq 3 ]]; echo hi > $S/a"
        self.assertEqual(values(numeric, "$S/a"), ["/tmp/claude-1000/x/a"])

    def test_a_name_assigned_inside_an_arithmetic_value_word_is_unproven(self):
        command = "S=/tmp/claude-1000/x; E=S\\=7; [[ E -eq 7 ]]; echo hi > $S/a"
        self.assertIsNone(values(command, "$S/a"))

    def test_a_name_hidden_by_an_escape_stays_in_assigned_names(self):
        self.assertIn("TMPDIR", ShellVariables("unset \\TMPDIR").assigned_names)
        self.assertIn("TMPDIR", ShellVariables("printf -vTMPDIR %s /etc").assigned_names)

    def test_a_format_string_or_another_programs_text_is_no_name_operand(self):
        loop = "for t in a b; do printf '%s\\n' x > /tmp/claude-1000/t_$t.log; done"
        self.assertEqual(values(loop, "/tmp/claude-1000/t_$t.log", step=1),
                         ["/tmp/claude-1000/t_a.log", "/tmp/claude-1000/t_b.log"])
        awk = "S=/tmp/claude-1000/x; awk '{print $1}' f; echo hi > $S/a"
        self.assertEqual(values(awk, "$S/a"), ["/tmp/claude-1000/x/a"])
        export = "S=/tmp/claude-1000/x; export PATH=$HOME/bin:$PATH; echo hi > $S/a"
        self.assertEqual(values(export, "$S/a"), ["/tmp/claude-1000/x/a"])

    def test_an_other_expansion_in_any_step_makes_the_command_unproven(self):
        self.assertIsNone(values("S=/tmp/x; echo ${P:-1}; echo hi > $S/a", "$S/a"))

    def test_a_trap_leaves_names_unproven(self):
        for trapping in ("trap '. /tmp/claude-1000/f' DEBUG", 'trap "$(cat /tmp/claude-1000/f)" DEBUG',
                         "trap `cat /tmp/claude-1000/f` DEBUG", "trap 'builtin . f' DEBUG",
                         "trap \"$(printf 'S\\x3d/home/brandon')\" DEBUG"):
            command = f"S=/tmp/claude-1000/x; {trapping}; echo hi > $S/a"
            self.assertIsNone(values(command, "$S/a"), command)

    def test_a_value_that_zsh_expands_with_an_equals_sign_is_unproven(self):
        for command in ("T==ls; echo hi > $T/a", "S=/tmp/a:=ls; echo hi > $S/a"):
            self.assertIsNone(values(command, command.rsplit("> ", 1)[-1]), command)

    def test_a_loop_variable_assigned_inside_its_own_body_is_unproven(self):
        command = "for d in a b; do d=/etc; echo > /tmp/$d/x; done"
        self.assertIsNone(values(command, "/tmp/$d/x", step=2))

    def test_an_assignment_inside_a_while_or_until_body_is_unproven(self):
        for command in ("while false; do S=/tmp/x; done; echo > $S/a", "until true; do S=/tmp/x; done; echo > $S/a"):
            self.assertIsNone(values(command, "$S/a"), command)

    def test_a_stray_do_or_done_is_unproven(self):
        for command in ("do S=/tmp/x; echo > $S/a", "S=/tmp/x; done; echo > $S/a",
                        "if true; then do S=/tmp/x; fi; echo > $S/a"):
            self.assertIsNone(values(command, "$S/a"), command)

    def test_exactly_the_combination_limit_is_proven_and_one_more_is_not(self):
        eight = " ".join(str(number) for number in range(8))
        at_limit = f"for a in {eight}; do for b in {eight}; do echo hi > /tmp/$a/$b; done; done"
        self.assertEqual(len(values(at_limit, "/tmp/$a/$b", step=2)), 64)
        five = " ".join(str(number) for number in range(5))
        thirteen = " ".join(str(number) for number in range(13))
        over = f"for a in {five}; do for b in {thirteen}; do echo hi > /tmp/$a/$b; done; done"
        self.assertIsNone(values(over, "/tmp/$a/$b", step=2))

    def test_a_hidden_group_or_glob_or_child_shell_heredoc_leaves_every_name_unproven(self):
        for command in ('( echo ")"; S=/tmp/x; true ); echo hi > $S/a', "echo `true\nS=/tmp/x\n`; echo hi > $S/a",
                        "S=/tmp/x; N=/x/S; ls *(e+'read $N:t <val'+); echo hi > $S/a",
                        "S=/tmp/x; N=/x/S; echo $N:t; echo hi > $S/a",
                        "S=/tmp/x; bash <<'EOF2'\necho hi > $S/a\nEOF2",
                        "echo '`' `\nS=/tmp/x\n` '`'; echo hi > $S/a",
                        "echo \\` `\nS=/tmp/x\n` \\`; echo hi > $S/a",
                        'echo "\\`" `\nS=/tmp/x\n` "\\`"; echo hi > $S/a',
                        "( echo }; S=/tmp/x; true ); echo hi > $S/a",
                        "( echo a }\nS=/tmp/x\n); echo hi > $S/a",
                        "( ls; echo } }; S=/tmp/x; true ); echo hi > $S/a"):
            self.assertIsNone(values(command, "$S/a"), command)

    def test_assigned_names_lists_every_name_the_command_sets(self):
        variables = ShellVariables("S=/tmp/x; for d in a; do echo; done; N=1; unset TMPDIR")
        self.assertLessEqual({"S", "d", "N", "TMPDIR"}, variables.assigned_names)
        self.assertNotIn("X", variables.assigned_names)


if __name__ == "__main__":
    unittest.main()
