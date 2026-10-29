"""A lib module and handback.py never import a hook module: a hook imports them, so the import would be a cycle, and a
hook's own checks would load inside every importer."""
import ast
import json
import pathlib
import re
import unittest

import toolkit_paths

HOOK_SCRIPT = re.compile(r"scripts/[\w/-]+\.py")
HANDBACK = toolkit_paths.REVIEW_DIR / "handback.py"


def hook_modules():
    """The module names of the Python scripts that settings.json registers as hooks."""
    settings = json.loads((toolkit_paths.CLAUDE_DIR / "settings.json").read_text())
    commands = [hook.get("command", "") for entries in settings.get("hooks", {}).values()
                for entry in entries for hook in entry.get("hooks", [])]
    return {pathlib.Path(script).stem for command in commands for script in HOOK_SCRIPT.findall(command)}


def imported_modules(path):
    """Every module name the file imports, at its top or inside a function."""
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def import_closure(roots, hooks):
    """The roots and every non-hook module in the review or lib folder they import, directly or through another."""
    found = set(roots)
    pending = list(roots)
    while pending:
        path = pending.pop()
        for module in imported_modules(path) - hooks:
            for folder in (toolkit_paths.REVIEW_DIR, toolkit_paths.LIB_DIR):
                local = folder / f"{module}.py"
                if local.exists() and local not in found:
                    found.add(local)
                    pending.append(local)
    return found


class HookModuleImportTest(unittest.TestCase):
    def test_settings_name_the_review_hooks(self):
        self.assertLessEqual({"review_loop_gate", "handback", "open_child_gate"}, hook_modules())

    def test_handback_closure_holds_its_review_and_lib_imports(self):
        closure_names = {path.name for path in import_closure([HANDBACK], hook_modules())}

        self.assertLessEqual({"handback.py", "full_check.py", "handback_store.py", "loop_transcript.py"}, closure_names)

    def test_no_lib_module_or_handback_imports_a_hook_module(self):
        hooks = hook_modules()
        roots = [HANDBACK, *toolkit_paths.LIB_DIR.glob("*.py")]
        importers = sorted(import_closure(roots, hooks))

        offenders = [f"{path.name} imports {module}" for path in importers
                     for module in sorted(imported_modules(path) & (hooks - {path.stem}))]

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
