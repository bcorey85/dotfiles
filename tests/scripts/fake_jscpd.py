"""A stand-in jscpd command for tests of the scripts that read its JSON report.

`stub_command(directory, duplicates)` plants a script under `directory` and returns the `REFACTOR_JSCPD_CMD`
value that runs it. The script writes `jscpd-report.json` into the folder its `--output` argument names, as
jscpd 5 does, records its argv and cwd in `directory/jscpd_call.txt`, and exits with `exit_code`.

`duplicate(first, second, clone_format)` builds one report entry from two `(name, start, end)` sites, with the
field names a real 5.4.3 report uses.
"""
import json
import shlex
import sys

STUB_SOURCE = """import json, os, pathlib, sys
arguments = sys.argv[1:]
pathlib.Path({record!r}).write_text(' '.join(arguments) + '\\n' + os.getcwd())
output_dir = pathlib.Path(arguments[arguments.index('--output') + 1])
(output_dir / 'jscpd-report.json').write_text({report!r})
sys.exit({exit_code})
"""


def fragment(name, start, end):
    return {"name": name, "start": start, "end": end,
            "startLoc": {"line": start, "column": 0, "position": 0},
            "endLoc": {"line": end, "column": 0, "position": 0}}


def duplicate(first, second, clone_format="python"):
    return {"format": clone_format, "lines": first[2] - first[1], "tokens": 50, "kind": "exact",
            "firstFile": fragment(*first), "secondFile": fragment(*second)}


def stub_command(directory, duplicates, exit_code=0, report_text=None):
    """`report_text` replaces the JSON report body, to plant a misshapen one."""
    if report_text is None:
        report_text = json.dumps({"duplicates": duplicates, "statistics": {}})
    source = STUB_SOURCE.format(record=str(directory / "jscpd_call.txt"), report=report_text, exit_code=exit_code)
    stub = directory / "jscpd_stub.py"
    stub.write_text(source)
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(stub))}"
