"""Checks that the script-tests workflow runs for every stowed script a test file exercises."""
import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "script-tests.yml"
STOWED_SCRIPT = re.compile(r'"scripts"\s*/\s*"\.local"\s*/\s*"bin"\s*/\s*"([^"]+)"')


def workflow_path_globs(event):
    """Return the quoted globs under `<event>:` / `paths:` in the workflow."""
    globs = []
    in_event = False
    in_paths = False
    for line in WORKFLOW.read_text().splitlines():
        if re.match(r"^\S", line):
            in_event = False
            in_paths = False
        if re.match(r"^  \S", line):
            in_event = line.strip() == event + ":"
            in_paths = False
        if in_event and line.strip() == "paths:":
            in_paths = True
            continue
        if in_event and in_paths:
            match = re.match(r'^\s+-\s+"([^"]+)"\s*$', line)
            if match:
                globs.append(match.group(1))
    return globs


def glob_covers(glob, path):
    if glob.endswith("/**"):
        return path.startswith(glob[:-2])
    return glob == path


class ScriptTestsWorkflowTest(unittest.TestCase):
    def test_every_stowed_script_under_test_triggers_the_workflow(self):
        tested_scripts = set()
        for test_file in sorted((REPO / "tests" / "scripts").glob("test_*.py")):
            for name in STOWED_SCRIPT.findall(test_file.read_text()):
                tested_scripts.add("scripts/.local/bin/" + name)
        self.assertTrue(tested_scripts, "no test builds a scripts/.local/bin path")

        for event in ("push", "pull_request"):
            globs = workflow_path_globs(event)
            self.assertTrue(globs, event + " has no paths list")
            for script in sorted(tested_scripts):
                covered = any(glob_covers(glob, script) for glob in globs)
                self.assertTrue(covered, script + " is tested but " + event + " paths do not cover it")


if __name__ == "__main__":
    unittest.main()
