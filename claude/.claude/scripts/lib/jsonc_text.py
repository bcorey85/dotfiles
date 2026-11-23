"""jsonc_text.py: JSON text that holds comments and trailing commas, as a .oxlintrc.json may."""
import json
import re

JSON_STRING = r'"(?:\\.|[^"\\])*"'
# The string alternative comes first, so a `//` or a comma inside a string is never read as a comment or a
# trailing comma.
STRING_OR_COMMENT = re.compile(JSON_STRING + r"|//[^\n]*|/\*.*?\*/", re.DOTALL)
STRING_OR_TRAILING_COMMA = re.compile(JSON_STRING + r"|,(?=\s*[}\]])")


def keep_strings(match):
    """The matched text when it is a string, else one space."""
    token = match.group(0)
    return token if token.startswith('"') else " "


def parse_jsonc(text):
    """The value `text` holds, read as JSON after its comments and trailing commas are cut. Raises
    json.JSONDecodeError when what is left is not JSON."""
    without_comments = STRING_OR_COMMENT.sub(keep_strings, text)
    plain_json = STRING_OR_TRAILING_COMMA.sub(keep_strings, without_comments)
    return json.loads(plain_json)
