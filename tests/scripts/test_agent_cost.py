"""agent-cost: SPEND reads the ledger through a stub `ledger` on PATH; PEAK reads transcripts."""
import datetime
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / ".local" / "bin" / "agent-cost"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
PROJECTS = FIXTURES / "agent_cost_projects"
PEAK_EXPECTED = FIXTURES / "agent_cost_peak_expected.txt"

STUB_LEDGER = """#!/bin/sh
for argument in "$@"; do printf '%s\\n' "$argument"; done >> "$STUB_ARGV_LOG"
cat "$STUB_ROWS"
exit "$STUB_EXIT"
"""
HEADER = ("machine\tagent_run_id\tagent\trepo\tmodel\tspawn_depth\tprice_status\tunpriced_reason\trequests\t"
          "cost_usd\toutput_tokens\tcache_write_tokens\tcache_read_tokens\tspeed_assumed\twrite_split_assumed")


def priced(run, agent="fixture-coder", repo="repo-alpha", model="claude-sonnet-5", depth=1, requests=3,
           cost="1.5", output=1000000, write=2000000, read=3000000, speed=1, split=2, machine="fixture-mac"):
    return "\t".join(str(field) for field in (machine, run, agent, repo, model, depth, "priced", "", requests, cost,
                                              output, write, read, speed, split))


def unpriced(run, model, status, reason, requests, agent="fixture-coder", repo="repo-alpha", machine="fixture-mac"):
    return "\t".join(str(field) for field in (machine, run, agent, repo, model, 1, status, reason, requests, "",
                                              "", "", "", 0, 0))


def table_rows(output):
    """Table rows keyed by their first column, each a list of the remaining fields."""
    lines = output.split("\n\n")[0].splitlines()[1:]
    return {line.split()[0]: line.split()[1:] for line in lines}


class AgentCostTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        root = pathlib.Path(scratch.name)
        self.root = root
        self.stub_dir = root / "bin"
        self.stub_dir.mkdir()
        stub = self.stub_dir / "ledger"
        stub.write_text(STUB_LEDGER)
        stub.chmod(0o755)
        self.argv_log = root / "argv.log"
        self.rows_file = root / "rows.tsv"
        self.ledger_root = root / "ledger-root"
        (self.ledger_root / "config").mkdir(parents=True)
        (self.ledger_root / "config" / "machine").write_bytes(b"fixture-mac\r\n")
        self.home = root / "home"
        self.home.mkdir()
        self.jq_dir = str(pathlib.Path(shutil.which("jq")).parent)
        self.stub_exit = "0"

    def plant(self, *rows):
        self.rows_file.write_text("\n".join((HEADER,) + rows) + "\n")

    def run_script(self, *arguments, path=None, projects=str(PROJECTS), ledger_root=None):
        environment = {
            "PATH": path if path is not None else "%s:%s:/usr/bin:/bin" % (self.stub_dir, self.jq_dir),
            "HOME": str(self.home),
            "LC_ALL": "C",
            "AGENT_LEDGER_ROOT": str(self.ledger_root if ledger_root is None else ledger_root),
            "CLAUDE_PROJECTS_DIR": projects,
            "STUB_ARGV_LOG": str(self.argv_log),
            "STUB_ROWS": str(self.rows_file),
            "STUB_EXIT": self.stub_exit,
        }
        return subprocess.run([str(SCRIPT)] + list(arguments), capture_output=True, text=True, env=environment)

    def sent_arguments(self):
        return self.argv_log.read_text() if self.argv_log.exists() else ""

    def test_spend_groups_cost_by_agent_from_ledger_rows(self):
        self.plant(priced("run-1", agent="agent-a", cost="1.5"),
                   priced("run-2", agent="agent-a", cost="0.5"),
                   priced("run-3", agent="agent-b", cost="2.0"))

        spend_report = self.run_script("--spend")

        self.assertEqual(spend_report.returncode, 0, spend_report.stderr)
        agent_rows = table_rows(spend_report.stdout)
        self.assertEqual(agent_rows["agent-a"][:3], ["2", "2.00", "1.000"])
        self.assertEqual(agent_rows["agent-b"][:3], ["1", "2.00", "2.000"])
        self.assertIn("3 dispatches, $4.00, mean $1.333", spend_report.stdout)
        self.assertIn("billed volume: 3.00M output, 6.00M cache write, 9.00M cache read", spend_report.stdout)
        self.assertIn("prices: ledger model_price (registry/rules/prices.toml); assumed: 3 requests at standard "
                      "speed, 6 cache writes at the 5m rate", spend_report.stdout)
        self.assertNotIn("UNPRICED", spend_report.stdout)

    def test_spend_groups_by_repo_model_and_depth(self):
        self.plant(priced("run-1", repo="repo-alpha", model="claude-sonnet-5", depth=1),
                   priced("run-2", repo="repo-beta", model="claude-opus-5", depth=2),
                   priced("run-3", repo="repo-beta", model="claude-opus-5", depth=2))
        expected = {"repo": {"repo-alpha": "1", "repo-beta": "2"},
                    "model": {"claude-sonnet-5": "1", "claude-opus-5": "2"},
                    "depth": {"1": "1", "2": "2"}}

        for grouping, counts in expected.items():
            with self.subTest(grouping=grouping):
                spend_report = self.run_script("--spend", "--by", grouping)

                self.assertEqual(spend_report.returncode, 0, spend_report.stderr)
                agent_rows = table_rows(spend_report.stdout)
                self.assertEqual({key: fields[0] for key, fields in agent_rows.items()}, counts)

    def test_spend_counts_dispatches_not_requests(self):
        self.plant(priced("run-1", model="claude-sonnet-5", requests=40),
                   priced("run-1", model="claude-opus-5", requests=10))

        spend_report = self.run_script("--spend")

        self.assertEqual(table_rows(spend_report.stdout)["fixture-coder"][0], "1")
        self.assertIn("1 dispatches,", spend_report.stdout)

    def test_spend_ledger_error_exits_1(self):
        self.plant(priced("run-1"))
        self.stub_exit = "1"

        spend_report = self.run_script("--spend")

        self.assertEqual(spend_report.returncode, 1)
        self.assertIn("ledger query failed", spend_report.stderr)
        self.assertEqual(spend_report.stdout, "")

    def test_spend_reports_unpriced_requests_by_model_and_reason(self):
        self.plant(priced("run-1"),
                   unpriced("run-2", "claude-fixture-unpriced", "unpriced", "no_price_row", 4),
                   unpriced("run-3", "claude-sonnet-5", "tokens_null", "", 2))

        spend_report = self.run_script("--spend")

        self.assertEqual(spend_report.returncode, 0, spend_report.stderr)
        self.assertIn("UNPRICED: 6 requests excluded:", spend_report.stdout)
        self.assertIn("claude-fixture-unpriced(no_price_row)(4)", spend_report.stdout)
        self.assertIn("claude-sonnet-5(tokens_null)(2)", spend_report.stdout)

    def test_spend_repo_filter_applies_in_awk_not_sql(self):
        self.plant(priced("run-1", agent="agent-a", repo="repo-alpha"),
                   priced("run-2", agent="agent-b", repo="repo-beta"))

        spend_report = self.run_script("--spend", "--repo", "repo-alpha")

        self.assertEqual(list(table_rows(spend_report.stdout)), ["agent-a"])
        self.assertNotIn("repo-alpha", self.sent_arguments())
        self.assertNotIn("fixture-mac", self.sent_arguments())

    def test_since_epoch_puts_iso_cutoff_in_query(self):
        self.plant(priced("run-1"))
        epoch = 1760000000
        iso = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        self.run_script("--spend", "--since", "@%d" % epoch)
        with_cutoff = self.sent_arguments()
        self.argv_log.unlink()
        self.run_script("--spend")
        without_cutoff = self.sent_arguments()

        self.assertIn("AND r.run_start >= '%s'" % iso, with_cutoff)
        self.assertNotIn("run_start >=", without_cutoff)

    def test_rates_flag_is_rejected(self):
        spend_report = self.run_script("--spend", "--rates", "opus:15:75")

        self.assertEqual(spend_report.returncode, 2)
        self.assertIn("unknown argument --rates", spend_report.stderr)

    def test_script_holds_no_rate_table(self):
        text = SCRIPT.read_text()

        for fragment in ("DEFAULT_RATES", "CACHE_WRITE_MULT", "CACHE_READ_MULT", "AGENT_COST_RATES", "--rates"):
            self.assertNotIn(fragment, text)

    def test_spend_without_ledger_exits_1(self):
        empty_dir = self.root / "empty"
        empty_dir.mkdir()

        spend_report = self.run_script("--spend", path="%s:/usr/bin:/bin" % empty_dir)

        self.assertEqual(spend_report.returncode, 1)
        self.assertIn("ledger", spend_report.stderr)
        self.assertEqual(spend_report.stdout, "")

    def test_peak_mode_never_calls_ledger(self):
        self.plant(priced("run-1"))

        spend_report = self.run_script()

        self.assertEqual(spend_report.returncode, 0, spend_report.stderr)
        self.assertEqual(self.sent_arguments(), "")

    def test_peak_output_matches_master(self):
        spend_report = self.run_script()

        self.assertEqual(spend_report.returncode, 0, spend_report.stderr)
        self.assertEqual(spend_report.stdout.encode(), PEAK_EXPECTED.read_bytes())

    def test_spend_counts_only_local_machine_rows(self):
        self.plant(priced("run-1", agent="agent-a", cost="1.0"),
                   priced("run-9", agent="agent-other", cost="900.0", machine="other-mac"),
                   unpriced("run-8", "claude-elsewhere", "unpriced", "no_price_row", 7, machine="other-mac"))

        spend_report = self.run_script("--spend")

        self.assertEqual(list(table_rows(spend_report.stdout)), ["agent-a"])
        self.assertIn("1 dispatches, $1.00", spend_report.stdout)
        self.assertNotIn("UNPRICED", spend_report.stdout)

    def test_spend_without_machine_file_exits_1(self):
        self.plant(priced("run-1"))
        empty_root = self.root / "no-machine"
        empty_root.mkdir()

        spend_report = self.run_script("--spend", ledger_root=empty_root)

        self.assertEqual(spend_report.returncode, 1)
        self.assertIn("no ledger machine file", spend_report.stderr)

    def test_spend_ignores_missing_projects_dir(self):
        self.plant(priced("run-1"))

        spend_report = self.run_script("--spend", projects=str(self.root / "does-not-exist"))

        self.assertEqual(spend_report.returncode, 0, spend_report.stderr)
        self.assertIn("1 dispatches,", spend_report.stdout)

    def test_spend_with_only_unpriced_rows_prints_no_dollar_total(self):
        self.plant(unpriced("run-1", "claude-fixture-unpriced", "unpriced", "no_price_row", 3))

        spend_report = self.run_script("--spend")

        self.assertEqual(spend_report.returncode, 0, spend_report.stderr)
        self.assertIn("no priced dispatches in range", spend_report.stdout)
        self.assertIn("UNPRICED: 3 requests excluded:", spend_report.stdout)
        self.assertNotIn("$", spend_report.stdout)

    def test_spend_with_no_rows_prints_no_dispatches_and_no_dollar(self):
        self.plant()

        spend_report = self.run_script("--spend")

        self.assertEqual(spend_report.returncode, 0, spend_report.stderr)
        self.assertIn("agent-cost: no dispatches in range", spend_report.stdout)
        self.assertNotIn("$", spend_report.stdout)

    def test_spend_reads_machine_file_under_home_when_no_ledger_root_is_set(self):
        self.plant(priced("run-1", agent="agent-a", cost="1.0"),
                   priced("run-9", agent="agent-other", cost="900.0", machine="other-mac"))
        machine_dir = self.home / ".config" / "agent-ledger"
        machine_dir.mkdir(parents=True)
        (machine_dir / "machine").write_text("fixture-mac\n")

        spend_report = self.run_script("--spend", ledger_root="")

        self.assertEqual(spend_report.returncode, 0, spend_report.stderr)
        self.assertEqual(list(table_rows(spend_report.stdout)), ["agent-a"])

    def test_spend_with_empty_machine_file_exits_1(self):
        self.plant(priced("run-1"))
        (self.ledger_root / "config" / "machine").write_bytes(b"")

        spend_report = self.run_script("--spend")

        self.assertEqual(spend_report.returncode, 1)
        self.assertIn("no ledger machine file", spend_report.stderr)

    def test_spend_prints_column_header_and_each_agents_share(self):
        self.plant(priced("run-1", agent="agent-a", cost="1.5"),
                   priced("run-2", agent="agent-a", cost="0.5"),
                   priced("run-3", agent="agent-b", cost="2.0"))

        spend_report = self.run_script("--spend")

        self.assertEqual(spend_report.stdout.splitlines()[0].split(),
                         ["agent", "n", "cost$", "mean$", "outM", "cwrtM", "creadM", "share"])
        self.assertEqual(table_rows(spend_report.stdout)["agent-a"][6], "50.0%")

    def test_spend_repo_filter_is_an_extended_regex(self):
        self.plant(priced("run-1", agent="agent-a", repo="repo-alpha"),
                   priced("run-2", agent="agent-b", repo="repo-alpha-two"),
                   priced("run-3", agent="agent-c", repo="repo-beta"))

        spend_report = self.run_script("--spend", "--repo", "alpha$")

        self.assertEqual(list(table_rows(spend_report.stdout)), ["agent-a"])

    def test_days_puts_iso_cutoff_in_query(self):
        self.plant(priced("run-1"))
        days = 3
        expected = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)

        self.run_script("--spend", "--days", str(days))
        sent = self.sent_arguments()
        self.argv_log.unlink()
        self.run_script("--spend")
        without_cutoff = self.sent_arguments()

        prefix = "AND r.run_start >= '"
        self.assertIn(prefix, sent)
        stamp = sent.split(prefix, 1)[1].split("'", 1)[0]
        cutoff = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
        self.assertLess(abs((cutoff - expected).total_seconds()), 120)
        self.assertNotIn("run_start >=", without_cutoff)


if __name__ == "__main__":
    unittest.main()
