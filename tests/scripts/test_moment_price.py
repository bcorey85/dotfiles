"""Tests for tools/moment_price.py: one priced line per moment, from an export file or from the ledger."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from toolkit_paths import LIB_DIR, TOOLS_DIR

sys.path.insert(0, str(LIB_DIR))
import script_utils

SCRIPT = pathlib.Path(os.environ.get("MOMENT_PRICE_PATH") or TOOLS_DIR / "moment_price.py")
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
RETRO = FIXTURES / "moment_price_retro_session.md"
ORDERS = FIXTURES / "moment_price_retro_session_orders.md"
SESSION_LINE = "# Session 7f3a2c: a title (repo: some-repo)\n"
SINCE = "2026-11-22T14:55:42.777Z"
UNTIL = "2026-11-22T14:58:10.000Z"
LIVE_HEADER = "ts\tmodel\tinput_tokens\tcache_creation_tokens\tcache_read_tokens\toutput_tokens\tduration_ms\n"
FIRST_ROW_TS = "2026-11-22T14:55:50.000Z"
LAST_ROW_TS = "2026-11-22T14:58:00.000Z"
LIVE_ROWS = (f"{LIVE_HEADER}"
             f"{FIRST_ROW_TS}\topus\t100\t50\t1000\t20\t4000\n"
             f"{LAST_ROW_TS}\topus\t10\t0\t2000\t5\t4000\n")
# A one-block moment: the request row is stamped when the request ended, after the block's own time.
ONE_BLOCK_SESSION = "74021271-80fa-4df9-9ce4-9e067e2847ee"
ONE_BLOCK_SINCE = "2026-11-22T14:55:31.043Z"
ONE_BLOCK_UNTIL = "2026-11-22T14:55:33.322Z"
ONE_BLOCK_ROWS = f"{LIVE_HEADER}2026-11-22T14:55:33.340Z\topus\t7\t3\t900\t40\t4228\n"
# Three requests whose blocks sit at 08.841, 11.119 and 11.531, and 15.260; rows are stamped at each request's end.
THREE_REQUEST_SESSION = "830dde5d-1ee4-4874-8eda-2935f0fd379a"
THREE_REQUEST_SINCE = "2026-11-08T23:51:08.841Z"
THREE_REQUEST_UNTIL = "2026-11-08T23:51:15.260Z"
THREE_REQUEST_ROWS = (f"{LIVE_HEADER}"
                      "2026-11-08T23:51:09.429Z\topus\t1\t0\t100\t10\t800\n"
                      "2026-11-08T23:51:11.721Z\topus\t2\t0\t200\t20\t2000\n"
                      "2026-11-08T23:51:15.606Z\topus\t4\t0\t400\t40\t1500\n")


class MomentPriceTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = pathlib.Path(folder.name)
        self.env = {**os.environ, "PATH": os.pathsep.join([str(self.folder), "/usr/bin", "/bin"]),
                    "CARGO_HOME": str(self.folder / "no-cargo"), script_utils.LEDGER_BACKOFF_ENV: "0"}

    def run_script(self, *args):
        command = [sys.executable, str(SCRIPT), *map(str, args)]
        return subprocess.run(command, env=self.env, capture_output=True, text=True, timeout=60)

    def export(self, text):
        export_file = self.folder / "export.md"
        export_file.write_text(text)
        return export_file

    def plant_ledger(self, body):
        stub = self.folder / "ledger"
        stub.write_text("#!/bin/sh\n" + body)
        stub.chmod(0o755)

    def live_args(self, session="7f3a-2c"):
        return ["price", "--session", session, "--since", SINCE, "--until", UNTIL]

    def test_both_real_fixtures_pass_check(self):
        for fixture, count in ((RETRO, 18), (ORDERS, 17)):
            with self.subTest(fixture.name):
                done = self.run_script("check", fixture)

                self.assertEqual((0, f"ok: {count} blocks\n"), (done.returncode, done.stdout))

    def test_a_range_of_opus_blocks_is_priced(self):
        done = self.run_script("price", RETRO, "1-6")

        expected = ("blocks 1-6 · 6 calls · 7 min · 167,480 tokens"
                    " · opus 16,550 fresh / 149,550 cache read / 1,380 output\n")
        self.assertEqual((0, expected), (done.returncode, done.stdout))

    def test_one_block_is_named_by_its_number(self):
        done = self.run_script("price", RETRO, "7")

        expected = ("blocks 7-7 · 1 calls · 0 min · 48,400 tokens"
                    " · sonnet 6,000 fresh / 40,000 cache read / 2,400 output\n")
        self.assertEqual(expected, done.stdout)

    def test_a_user_block_adds_time_but_no_call_or_tokens(self):
        done = self.run_script("price", RETRO, "0-8")

        expected = ("blocks 0-8 · 8 calls · 13 min · 264,670 tokens"
                    " · opus 16,550 fresh / 149,550 cache read / 1,380 output"
                    " · sonnet 6,300 fresh / 88,400 cache read / 2,490 output\n")
        self.assertEqual(expected, done.stdout)

    def test_models_are_ordered_by_total_tokens_largest_first(self):
        text = (SESSION_LINE + "## Block 1 · 09:01 · sonnet · 1 / 1 / 1\n## Block 2 · 09:02 · opus · 100 / 100 / 100\n")

        done = self.run_script("price", self.export(text), "1-2")

        expected = ("blocks 1-2 · 2 calls · 1 min · 303 tokens · opus 100 fresh / 100 cache read / 100 output"
                    " · sonnet 1 fresh / 1 cache read / 1 output\n")
        self.assertEqual(expected, done.stdout)

    def test_models_with_equal_totals_are_ordered_by_name(self):
        text = (SESSION_LINE + "## Block 1 · 09:01 · zeta · 1 / 1 / 1\n## Block 2 · 09:02 · alpha · 1 / 1 / 1\n")

        done = self.run_script("price", self.export(text), "1-2")

        expected = ("blocks 1-2 · 2 calls · 1 min · 6 tokens · alpha 1 fresh / 1 cache read / 1 output"
                    " · zeta 1 fresh / 1 cache read / 1 output\n")
        self.assertEqual(expected, done.stdout)

    def test_json_carries_the_same_totals(self):
        done = self.run_script("price", RETRO, "7-9", "--json")

        price = json.loads(done.stdout)
        self.assertEqual((3, 2, {"sonnet": {"fresh": 8100, "cache_read": 137100, "output": 3690}}),
                         (price["calls"], price["minutes"], price["models"]))

    def test_each_bad_shape_stops_with_file_line_and_expected_form(self):
        cases = {
            "bad header": (SESSION_LINE + "## Block 1 · 09:01 · opus · 4,200 / 18,000\n", "export.md:2",
                           "bad block header"),
            "out of order": (SESSION_LINE + "## Block 2 · 09:01 · user\n\n## Block 1 · 09:02 · user\n",
                             "export.md:4", "increasing order"),
            "repeated block number": (SESSION_LINE + "## Block 1 · 09:01 · user\n## Block 1 · 09:02 · user\n",
                                      "export.md:3", "increasing order"),
            "empty file": ("", "export.md:1", "missing session line"),
            "unknown heading": (SESSION_LINE + "## Notes\n", "export.md:2", "bad block header"),
            "no session line": ("## Block 1 · 09:01 · user\n", "export.md:1", "expected # Session <id>: <title>"),
            "user with tokens": (SESSION_LINE + "## Block 1 · 09:01 · user · 1 / 2 / 3\n", "export.md:2",
                                 "carries no tokens"),
            "assistant without tokens": (SESSION_LINE + "## Block 1 · 09:01 · opus\n", "export.md:2", "without tokens"),
            "hour out of range": (SESSION_LINE + "## Block 1 · 25:00 · user\n", "export.md:2", "bad time"),
            "minute out of range": (SESSION_LINE + "## Block 1 · 09:61 · user\n", "export.md:2", "bad time"),
        }
        for name, (text, where, reason) in cases.items():
            with self.subTest(name):
                done = self.run_script("check", self.export(text))

                self.assertEqual(1, done.returncode)
                self.assertIn(where, done.stderr.replace(str(self.folder) + "/", ""))
                self.assertIn(reason, done.stderr)
                self.assertEqual("", done.stdout)

    def test_a_bad_command_line_exits_2(self):
        cases = {
            "session without since": ["price", "--session", "7f3a-2c"],
            "session with a target": ["price", "--session", "7f3a-2c", "--since", SINCE, "--until", UNTIL, "extra"],
            "export with since": ["price", RETRO, "1-6", "--since", SINCE],
            "session with since and no until": ["price", "--session", "7f3a-2c", "--since", SINCE],
            "export with until": ["price", RETRO, "1-6", "--until", UNTIL],
            "price without a range": ["price", RETRO],
            "check with session": ["check", RETRO, "--session", "7f3a-2c"],
            "check with since": ["check", RETRO, "--since", SINCE],
            "check with until": ["check", RETRO, "--until", UNTIL],
            "check with extra args": ["check", RETRO, "extra"],
            "check with json": ["check", RETRO, "--json"],
        }
        for name, args in cases.items():
            with self.subTest(name):
                done = self.run_script(*args)

                self.assertEqual((2, ""), (done.returncode, done.stdout))
                self.assertIn("usage:", done.stderr)

    def test_a_bad_range_text_stops(self):
        cases = {"not a range": ("abc", "expected a block range"), "reversed": ("6-1", "first block is after the last")}
        for name, (range_text, reason) in cases.items():
            with self.subTest(name):
                done = self.run_script("price", RETRO, range_text)

                self.assertEqual((1, ""), (done.returncode, done.stdout))
                self.assertIn(reason, done.stderr)

    def test_a_range_outside_the_file_stops(self):
        done = self.run_script("price", RETRO, "5-40")

        self.assertEqual((1, ""), (done.returncode, done.stdout))
        self.assertIn("block 40 is not in the file", done.stderr)

    def test_a_missing_export_file_stops_with_a_message(self):
        missing = self.folder / "no-such-export.md"

        done = self.run_script("price", missing, "1-2")

        self.assertEqual((1, ""), (done.returncode, done.stdout))
        self.assertIn("cannot read", done.stderr)
        self.assertNotIn("Traceback", done.stderr)

    def test_a_range_whose_first_block_is_missing_stops(self):
        text = SESSION_LINE + "## Block 1 · 09:01 · user\n## Block 3 · 09:02 · user\n"

        done = self.run_script("price", self.export(text), "2-3")

        self.assertEqual((1, ""), (done.returncode, done.stdout))
        self.assertIn("block 2 is not in the file", done.stderr)

    def test_a_range_across_midnight_stops(self):
        text = SESSION_LINE + "## Block 1 · 23:50 · opus · 1 / 2 / 3\n## Block 2 · 00:10 · opus · 1 / 2 / 3\n"

        done = self.run_script("price", self.export(text), "1-2")

        self.assertEqual((1, ""), (done.returncode, done.stdout))
        self.assertIn("across midnight", done.stderr)

    def test_live_rows_are_summed_into_one_line(self):
        rows_for_printf = LIVE_ROWS.replace("\n", "\\n")
        wrong_query = "case \"$2\" in *\"where session = '7f3a-2c' and \"*) ;; *) echo wrong query >&2; exit 65;; esac"
        self.plant_ledger(f'[ "$1" = query ] || exit 64\n{wrong_query}\nprintf "{rows_for_printf}"\n')

        done = self.run_script(*self.live_args())

        expected = (f"{SINCE}..{UNTIL} · 2 calls · 2 min · 3,185 tokens"
                    " · opus 160 fresh / 3,000 cache read / 25 output\n")
        self.assertEqual((0, expected), (done.returncode, done.stdout))

    def plant_rows(self, rows):
        """A ledger stub that records its query text in query.txt and prints `rows`."""
        query_file = self.folder / "query.txt"
        self.plant_ledger(f'printf "%s" "$2" > "{query_file}"\nprintf "{rows.replace(chr(10), chr(92) + "n")}"\n')
        return query_file

    def test_the_window_is_written_in_the_ledger_form_in_utc(self):
        query_file = self.plant_rows(LIVE_ROWS)

        done = self.run_script("price", "--session", "7f3a-2c", "--since", "2026-11-22T09:00:00-05:00",
                               "--until", "2026-11-22T14:58:10Z")

        self.assertEqual(0, done.returncode, done.stderr)
        self.assertIn("ts >= '2026-11-22T14:00:00.000Z' and ts <= '2026-11-22T15:58:10.000Z'", query_file.read_text())

    def test_a_since_with_sub_millisecond_digits_rounds_up_and_an_until_rounds_down(self):
        query_file = self.plant_rows(LIVE_ROWS)

        done = self.run_script("price", "--session", "7f3a-2c", "--since", "2026-11-22T14:55:42.3135Z",
                               "--until", "2026-11-22T14:58:10.9995Z")

        self.assertEqual(0, done.returncode, done.stderr)
        self.assertIn("ts >= '2026-11-22T14:55:42.314Z' and ts <= '2026-11-22T15:58:10.999Z'", query_file.read_text())

    def test_a_since_at_whole_seconds_starts_at_the_first_millisecond_of_that_second(self):
        query_file = self.plant_rows(LIVE_ROWS)

        done = self.run_script("price", "--session", "7f3a-2c", "--since", "2026-11-22T14:55:42Z", "--until", UNTIL)

        self.assertEqual(0, done.returncode, done.stderr)
        self.assertIn("ts >= '2026-11-22T14:55:42.000Z'", query_file.read_text())

    def test_a_bad_timestamp_stops_before_the_ledger_runs(self):
        for bad in ("notatime", "2026-13-45T00:00:00Z"):
            with self.subTest(bad):
                done = self.run_script("price", "--session", "7f3a-2c", "--since", bad, "--until", UNTIL)

                self.assertEqual((1, ""), (done.returncode, done.stdout))
                self.assertIn("expected an ISO timestamp", done.stderr)

    def test_live_rows_of_two_models_are_split_and_ordered_by_total_tokens(self):
        rows = (f"{LIVE_HEADER}{FIRST_ROW_TS}\tsonnet\t5\t5\t500\t10\t4000\n"
                f"2026-11-22T14:56:00.000Z\topus\t100\t50\t1000\t20\t4000\n"
                f"{LAST_ROW_TS}\topus\t10\t0\t2000\t5\t4000\n")
        self.plant_rows(rows)

        done = self.run_script(*self.live_args())

        expected = (f"{SINCE}..{UNTIL} · 3 calls · 2 min · 3,705 tokens"
                    " · opus 160 fresh / 3,000 cache read / 25 output"
                    " · sonnet 10 fresh / 500 cache read / 10 output\n")
        self.assertEqual((0, expected), (done.returncode, done.stdout))

    def test_a_one_block_moment_finds_the_request_row_stamped_after_until(self):
        self.plant_rows(ONE_BLOCK_ROWS)

        done = self.run_script("price", "--session", ONE_BLOCK_SESSION, "--since", ONE_BLOCK_SINCE,
                               "--until", ONE_BLOCK_UNTIL)

        expected = (f"{ONE_BLOCK_SINCE}..{ONE_BLOCK_UNTIL} · 1 calls · 0 min · 950 tokens"
                    " · opus 10 fresh / 900 cache read / 40 output\n")
        self.assertEqual((0, expected, ""), (done.returncode, done.stdout, done.stderr))

    def test_every_request_that_overlaps_the_window_is_priced(self):
        self.plant_rows(THREE_REQUEST_ROWS)

        done = self.run_script("price", "--session", THREE_REQUEST_SESSION, "--since", THREE_REQUEST_SINCE,
                               "--until", THREE_REQUEST_UNTIL, "--json")

        price = json.loads(done.stdout)
        self.assertEqual((3, 7, 777), (price["calls"], price["models"]["opus"]["fresh"], price["tokens"]))

    def test_a_request_that_started_after_until_is_left_out(self):
        late_row = "2026-11-08T23:51:20.000Z\topus\t1000\t0\t0\t0\t1000\n"
        self.plant_rows(THREE_REQUEST_ROWS + late_row)

        done = self.run_script("price", "--session", THREE_REQUEST_SESSION, "--since", THREE_REQUEST_SINCE,
                               "--until", THREE_REQUEST_UNTIL, "--json")

        price = json.loads(done.stdout)
        self.assertEqual(3, price["calls"])

    def test_a_request_that_started_exactly_at_until_is_priced_and_one_millisecond_later_is_not(self):
        on_the_edge = "2026-11-22T14:58:12.000Z\topus\t7\t0\t0\t0\t2000\n"
        just_after = "2026-11-22T14:58:12.001Z\topus\t1000\t0\t0\t0\t2000\n"
        self.plant_rows(LIVE_ROWS + on_the_edge + just_after)

        done = self.run_script(*self.live_args(), "--json")

        price = json.loads(done.stdout)
        self.assertEqual((3, 167), (price["calls"], price["models"]["opus"]["fresh"]))

    def test_live_minutes_are_the_window_not_the_rows(self):
        self.plant_rows(ONE_BLOCK_ROWS)

        done = self.run_script("price", "--session", ONE_BLOCK_SESSION, "--since", "2026-11-22T14:55:00.000Z",
                               "--until", "2026-11-22T14:56:00.000Z", "--json")

        self.assertEqual(1, json.loads(done.stdout)["minutes"])

    def test_a_since_after_until_stops_before_the_ledger_runs(self):
        done = self.run_script("price", "--session", "7f3a-2c", "--since", UNTIL, "--until", SINCE)

        self.assertEqual((1, ""), (done.returncode, done.stdout))
        self.assertIn("--since is after --until; expected since <= until", done.stderr)

    def test_a_window_whose_only_row_started_after_until_is_a_stop(self):
        self.plant_rows(f"{LIVE_HEADER}2026-11-22T14:58:30.000Z\topus\t1\t0\t0\t0\t1000\n")

        done = self.run_script(*self.live_args())

        self.assertEqual((1, ""), (done.returncode, done.stdout))
        self.assertIn("no otel_api_request rows", done.stderr)

    def test_the_query_reads_the_duration_and_stops_one_hour_after_until(self):
        query_file = self.plant_rows(ONE_BLOCK_ROWS)

        self.run_script("price", "--session", ONE_BLOCK_SESSION, "--since", ONE_BLOCK_SINCE,
                        "--until", ONE_BLOCK_UNTIL)

        query = query_file.read_text()
        self.assertIn("duration_ms from otel_api_request", query)
        self.assertIn("ts <= '2026-11-22T15:55:33.322Z'", query)

    def test_json_on_the_live_path_carries_the_totals(self):
        self.plant_rows(LIVE_ROWS)

        done = self.run_script(*self.live_args(), "--json")

        price = json.loads(done.stdout)
        self.assertEqual((2, 2, {"opus": {"fresh": 160, "cache_read": 3000, "output": 25}}, 3185),
                         (price["calls"], price["minutes"], price["models"], price["tokens"]))

    def test_a_malformed_ledger_row_is_a_stop_naming_the_row(self):
        header = LIVE_ROWS.splitlines()[0]
        cases = {
            "wrong column count": f"{header}\n{FIRST_ROW_TS}\topus\t1\n",
            "token not a number": f"{header}\n{FIRST_ROW_TS}\topus\tx\t0\t0\t0\t10\n",
            "bad ts": f"{header}\nyesterday\topus\t1\t0\t0\t0\t10\n",
            "blank duration": f"{header}\n{FIRST_ROW_TS}\topus\t1\t0\t0\t0\t\n",
            "duration not a number": f"{header}\n{FIRST_ROW_TS}\topus\t1\t0\t0\t0\tNULL\n",
        }
        for name, rows in cases.items():
            with self.subTest(name):
                self.plant_rows(rows)

                done = self.run_script(*self.live_args())

                self.assertEqual((1, ""), (done.returncode, done.stdout))
                self.assertIn("ledger row 1", done.stderr)

    def test_a_window_with_no_rows_is_a_stop_not_a_zero_line(self):
        header_only = LIVE_ROWS.splitlines()[0]
        self.plant_ledger(f'printf "{header_only}\\n"\n')

        done = self.run_script(*self.live_args())

        self.assertEqual((1, ""), (done.returncode, done.stdout))
        self.assertIn("no otel_api_request rows", done.stderr)
        self.assertIn("rows may not be collected yet; rerun after `ledger collect`", done.stderr)
        self.assertIn('check with: ledger query "select', done.stderr)

    def test_a_missing_ledger_names_what_was_not_read_and_the_command(self):
        done = self.run_script(*self.live_args())

        self.assertEqual((1, ""), (done.returncode, done.stdout))
        self.assertIn("not read", done.stderr)
        self.assertIn('ledger query "select', done.stderr)

    def test_a_failing_ledger_is_a_stop(self):
        self.plant_ledger("echo broken >&2\nexit 3\n")

        done = self.run_script(*self.live_args())

        self.assertEqual((1, ""), (done.returncode, done.stdout))
        self.assertIn("broken", done.stderr)
        self.assertIn("not read", done.stderr)
        self.assertIn('ledger query "select', done.stderr)

    def test_a_session_id_that_could_carry_a_quote_is_refused_before_the_ledger_runs(self):
        done = self.run_script(*self.live_args("x'; drop table t; --"))

        self.assertEqual(1, done.returncode)
        self.assertIn("expected a session id", done.stderr)


if __name__ == "__main__":
    unittest.main()
