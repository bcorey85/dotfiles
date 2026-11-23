"""A scripts CLAUDE.md text and an owner bullet, shared by the tests of owner-line edits."""

SCRIPTS_MD = (
    "# Toolkit scripts\n\n## Owners\n\n- Plan text: `lib/plan_format.py`.\n"
    "- TOML files: `lib/toml_file.py` `read_toml`.\n\n## Data between steps\n\n- Steps pass JSON to each other.\n"
)
NEW_BULLET = "- A new fact: `lib/new_fact.py`.\n"
SCRIPTS_MD_WITH_NEW_BULLET = SCRIPTS_MD.replace("\n## Data", NEW_BULLET + "\n## Data")
