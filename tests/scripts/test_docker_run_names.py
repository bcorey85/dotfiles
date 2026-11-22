"""Checks for docker_run_names.py: which docker run steps carry no container name, and the fixed form of each."""
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import docker_run_names


class UnnamedDockerRunsTest(unittest.TestCase):
    def setUp(self):
        self.folder = pathlib.Path(tempfile.mkdtemp(prefix="docker-names-fixture-"))
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)

    def on_branch(self, branch):
        subprocess.run(["git", "init", "-q", str(self.folder)], check=True)
        subprocess.run(["git", "-C", str(self.folder), "symbolic-ref", "HEAD", f"refs/heads/{branch}"], check=True)

    def unnamed(self, command):
        return docker_run_names.unnamed_docker_runs(command, str(self.folder))

    def test_an_unnamed_run_gets_the_fixed_form(self):
        self.assertEqual(self.unnamed("docker run image cmd"),
                         ["docker run --rm --name <ticket>-<purpose> image cmd"])

    def test_a_run_that_has_rm_gets_one_rm(self):
        self.assertEqual(self.unnamed("docker run --rm -v /a:/b image"),
                         ["docker run --name <ticket>-<purpose> --rm -v /a:/b image"])

    def test_a_named_run_gives_nothing(self):
        for command in ("docker run --name x image", "docker run --name=x image", "docker run -v /a:/b --name x image"):
            with self.subTest(command=command):
                self.assertEqual(self.unnamed(command), [])

    def test_a_name_flag_after_the_image_belongs_to_the_container_command(self):
        self.assertEqual(self.unnamed("docker run image prog --name x"),
                         ["docker run --rm --name <ticket>-<purpose> image prog --name x"])

    def test_a_value_that_looks_like_the_image_does_not_end_the_options(self):
        self.assertEqual(self.unnamed("docker run -e A=b --name x image"), [])

    def test_the_container_run_form_and_podman_are_read(self):
        self.assertEqual(self.unnamed("docker container run image"),
                         ["docker container run --rm --name <ticket>-<purpose> image"])
        self.assertEqual(self.unnamed("podman run image"), ["podman run --rm --name <ticket>-<purpose> image"])

    def test_other_docker_calls_give_nothing(self):
        for command in ("docker compose run web pytest", "docker exec c cmd", "docker ps", "git run image"):
            with self.subTest(command=command):
                self.assertEqual(self.unnamed(command), [])

    def test_a_run_behind_a_wrapper_is_read(self):
        self.assertEqual(self.unnamed("timeout 60 docker run image"),
                         ["timeout 60 docker run --rm --name <ticket>-<purpose> image"])
        self.assertEqual(self.unnamed("FOO=1 docker run image"),
                         ["FOO=1 docker run --rm --name <ticket>-<purpose> image"])

    def test_quoted_words_stay_as_written(self):
        self.assertEqual(self.unnamed('docker run -v "$PWD/w" -v $PWD:/a image'),
                         ['docker run --rm --name <ticket>-<purpose> -v "$PWD/w" -v $PWD:/a image'])

    def test_a_value_option_outside_the_old_table_does_not_hide_the_name(self):
        for command in ("docker run --net mynet --name x image", "docker run --ipc host --name x image",
                        "podman run --pod p --name x image", "docker run -it -p80:80 --name x image",
                        "podman run --replace --name x image"):
            with self.subTest(command=command):
                self.assertEqual(self.unnamed(command), [])

    def test_a_boolean_option_does_not_swallow_the_name(self):
        options = ("-d", "-i", "-t", "-P", "-q", "--rm", "--init", "--privileged", "--read-only", "--detach",
                   "--interactive", "--tty", "--publish-all", "--quiet", "--sig-proxy", "--no-healthcheck",
                   "--oom-kill-disable")
        for option in options:
            with self.subTest(option=option):
                self.assertEqual(self.unnamed(f"docker run {option} --name x image"), [])

    def test_the_fixed_form_keeps_the_step_text(self):
        cases = {
            'docker run -v "$PWD":/app img > out.log':
                'docker run --rm --name <ticket>-<purpose> -v "$PWD":/app img > out.log',
            'docker run -e TOKEN="$TOKEN x" img > out.log':
                'docker run --rm --name <ticket>-<purpose> -e TOKEN="$TOKEN x" img > out.log',
            'docker run -v "$(pwd)":/w image': 'docker run --rm --name <ticket>-<purpose> -v "$(pwd)":/w image',
            "docker run image > out.log 2>&1": "docker run --rm --name <ticket>-<purpose> image > out.log 2>&1",
            "docker run img$(echo x)": "docker run --rm --name <ticket>-<purpose> img$(echo x)",
            "docker run --rm=true img": "docker run --name <ticket>-<purpose> --rm=true img",
            "echo $(docker run img)": "docker run --rm --name <ticket>-<purpose> img",
            "(docker run img)": "docker run --rm --name <ticket>-<purpose> img",
            "x=$(docker run img cmd) && echo $x": "docker run --rm --name <ticket>-<purpose> img cmd",
            "( cd /tmp && docker run img )": "docker run --rm --name <ticket>-<purpose> img",
            "echo $(docker run img) foo": "docker run --rm --name <ticket>-<purpose> img",
            "f $(docker run img) $(ls)": "docker run --rm --name <ticket>-<purpose> img",
            "echo $(docker run img sh -c 'a)b') z": "docker run --rm --name <ticket>-<purpose> img sh -c 'a)b'",
            "echo $(docker run img) > out": "docker run --rm --name <ticket>-<purpose> img",
            "(docker run img) > out 2>&1": "docker run --rm --name <ticket>-<purpose> img",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(self.unnamed(command), [expected])

    def test_the_ticket_comes_from_the_directory_the_step_runs_in(self):
        self.on_branch("ABC-12-x")
        sub = self.folder / "sub"
        sub.mkdir()
        elsewhere = pathlib.Path(tempfile.mkdtemp(prefix="docker-names-plain-"))
        self.addCleanup(shutil.rmtree, elsewhere, ignore_errors=True)
        self.assertEqual(docker_run_names.unnamed_docker_runs(f"cd {sub} && docker run image", str(elsewhere)),
                         ["docker run --rm --name ABC-12-<purpose> image"])

    def test_quoted_text_is_no_call(self):
        self.assertEqual(self.unnamed('echo "docker run image"'), [])

    def test_the_ticket_comes_from_the_branch(self):
        self.on_branch("ABC-12-desc")
        self.assertEqual(self.unnamed("docker run image"), ["docker run --rm --name ABC-12-<purpose> image"])

    def test_a_branch_with_no_ticket_keeps_the_placeholder(self):
        self.on_branch("feature")
        self.assertEqual(self.unnamed("docker run image"), ["docker run --rm --name <ticket>-<purpose> image"])

    def test_each_unnamed_run_of_a_command_is_listed(self):
        self.assertEqual(self.unnamed("docker run a && docker run --name x b; docker run c"),
                         ["docker run --rm --name <ticket>-<purpose> a",
                          "docker run --rm --name <ticket>-<purpose> c"])

    def test_a_run_inside_a_named_run_gets_a_form_for_the_inner_run(self):
        forms = self.unnamed("docker run --name x img1 $(docker run img2)")
        self.assertEqual(forms, ["docker run --rm --name <ticket>-<purpose> img2"])

    def test_an_unnamed_run_with_a_run_nested_in_it_gets_a_form_for_each(self):
        forms = self.unnamed("docker run img1 $(docker run img2) > out.txt")
        self.assertEqual(forms, ["docker run --rm --name <ticket>-<purpose> img1 $(docker run img2) > out.txt",
                                 "docker run --rm --name <ticket>-<purpose> img2"])

    def test_an_outer_image_that_prefixes_the_inner_image_keeps_its_own_form(self):
        forms = self.unnamed("docker run ubuntu $(docker run ubuntu:22.04)")
        self.assertEqual(forms, ["docker run --rm --name <ticket>-<purpose> ubuntu $(docker run ubuntu:22.04)",
                                 "docker run --rm --name <ticket>-<purpose> ubuntu:22.04"])

    def test_an_inner_image_ending_in_a_variable_does_not_hide_the_outer_form(self):
        forms = self.unnamed("docker run app $(docker run app$TAG)")
        self.assertEqual(forms, ["docker run --rm --name <ticket>-<purpose> app $(docker run app$TAG)",
                                 "docker run --rm --name <ticket>-<purpose> app$TAG"])

    def test_a_nested_run_with_the_outer_image_is_built_from_its_words(self):
        forms = self.unnamed("docker run img $(docker run img)")
        self.assertEqual(len(forms), 2)
        self.assertEqual(forms[1], "docker run --rm --name <ticket>-<purpose> img")

    def test_a_group_word_is_no_part_of_the_fixed_form(self):
        cases = {
            "for x in 1; do docker run img; done": "docker run --rm --name <ticket>-<purpose> img",
            "if true; then docker run img; fi": "docker run --rm --name <ticket>-<purpose> img",
            "if docker run img; then echo ok; fi": "docker run --rm --name <ticket>-<purpose> img",
            "if true; then\tdocker run img; fi": "docker run --rm --name <ticket>-<purpose> img",
            "{ docker run img; }": "docker run --rm --name <ticket>-<purpose> img",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(self.unnamed(command), [expected])

    def test_a_help_call_starts_no_container(self):
        self.assertEqual(self.unnamed("docker run --help"), [])

    def test_a_help_flag_after_the_image_belongs_to_the_container_command(self):
        forms = self.unnamed("docker run img --help")
        self.assertEqual(forms, ["docker run --rm --name <ticket>-<purpose> img --help"])

    def test_a_run_whose_quotes_the_raw_reader_cannot_close_is_built_from_its_words(self):
        forms = self.unnamed('docker run -e A=" x " img')
        self.assertEqual(forms, ["docker run --rm --name <ticket>-<purpose> -e 'A= x ' img"])

    def test_a_step_with_an_unknown_folder_gets_no_branch_ticket(self):
        self.on_branch("ABC-12-x")
        self.assertEqual(self.unnamed('cd "$X" && docker run img'), ["docker run --rm --name <ticket>-<purpose> img"])

    def test_a_non_docker_step_with_an_unclosable_quote_is_not_read(self):
        self.assertEqual(self.unnamed('git log --format="%h %s " -3'), [])

    def test_a_run_with_rm_false_gets_rm_and_loses_the_false_word(self):
        fixed = "docker run --rm --name <ticket>-<purpose>"
        cases = {
            "docker run --rm=false img": f"{fixed} img",
            "docker run\t--rm=false img": f"{fixed} img",
            'docker run "--rm=false" img': f"{fixed} img",
            "docker run -v /a:/b --rm=false -e A=b img": f"{fixed} -v /a:/b -e A=b img",
            "docker run --rm=false -e A=b --rm=false img": f"{fixed} -e A=b img",
            "docker run -e 'A= --rm=false' --rm=false img": f"{fixed} -e 'A= --rm=false' img",
            "docker run img --rm=false": f"{fixed} img --rm=false",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(self.unnamed(command), [expected])

    def test_a_run_whose_text_cannot_be_matched_is_built_from_its_words(self):
        step = "docker run --rm=false -v a img"
        raw_words = ["docker", "run", "--rm=false", "-v", "a", "img"]
        span = docker_run_names.RunSpan(first=0, run_end=2, image_end=5)
        form = docker_run_names.fixed_form(step.replace(" -v", "\\\n -v"), raw_words, span, str(self.folder))
        self.assertEqual(form, "docker run --rm --name <ticket>-<purpose> -v a img")

    def test_a_rebuilt_form_drops_the_closer_of_its_subshell(self):
        raw_words = ["docker", "run", "--rm=false", "-v", "a", "img)"]
        span = docker_run_names.RunSpan(first=0, run_end=2, image_end=5)
        form = docker_run_names.fixed_form("no match", raw_words, span, str(self.folder))
        self.assertEqual(form, "docker run --rm --name <ticket>-<purpose> -v a img")

    def test_an_empty_name_counts_as_no_name(self):
        for command in ("docker run --name= img", 'docker run --name "" img'):
            with self.subTest(command=command):
                self.assertEqual(self.unnamed(command), ["docker run --rm --name <ticket>-<purpose> img"])

    def test_a_name_option_with_no_value_counts_as_no_name(self):
        self.assertEqual(self.unnamed("docker run --name"), ["docker run --rm --name <ticket>-<purpose>"])

    def test_the_last_name_option_is_the_one_docker_keeps(self):
        self.assertEqual(self.unnamed("docker run --name= --name x img"), [])
        self.assertEqual(self.unnamed("docker run --name=x --name= img"),
                         ["docker run --rm --name <ticket>-<purpose> img"])

    def test_the_value_skip_rule_reads_the_word_after_name_as_its_value(self):
        # Docker rejects this command; the test pins how the reader walks options, not intended use.
        self.assertEqual(self.unnamed("docker run --name -d image"), [])

    def test_docker_global_options_and_clusters_are_read(self):
        self.assertEqual(self.unnamed("docker --context x run --name n img"), [])
        self.assertEqual(self.unnamed("docker -H tcp://x run --name n img"), [])
        self.assertEqual(
            self.unnamed("docker -H tcp://x run img"),
            ["docker -H tcp://x run --rm --name <ticket>-<purpose> img"],
        )
        self.assertEqual(self.unnamed("docker run -dp 80:80 --name n img"), [])
        self.assertEqual(self.unnamed("docker run --log-driver json img"),
                         ["docker run --rm --name <ticket>-<purpose> --log-driver json img"])

    def test_a_program_path_is_read_as_the_program(self):
        self.assertEqual(self.unnamed("/usr/bin/docker run img"),
                         ["/usr/bin/docker run --rm --name <ticket>-<purpose> img"])

    def test_an_unreadable_step_alone_gives_nothing(self):
        self.assertEqual(self.unnamed("echo 'unterminated; docker run img"), [])

    def test_a_readable_run_is_listed_beside_an_unreadable_step(self):
        self.assertEqual(self.unnamed("docker run img; echo $("),
                         ["docker run --rm --name <ticket>-<purpose> img"])


if __name__ == "__main__":
    unittest.main()
