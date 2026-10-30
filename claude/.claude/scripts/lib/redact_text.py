"""redact_text.py: plain-text redaction helpers. They read any text and no module table or rule."""
import re

HOME_PLACEHOLDER = "/home/captured"
HOME_PATH = re.compile(r"(?:/home|/Users)/[^/\s\"'`]+")
# An email address, a credential word, a well-known token prefix, or a long unbroken token-like string.
SECRET_TEXT = re.compile(
    r"[\w.+-]+@[\w-]+\.[\w.-]+|\b(?:token|secret|password|passwd|api[_-]?key|bearer|credential)s?\b"
    r"|\b(?:sk|pk|ghp|gho|xox[bp]|AKIA)[-_A-Za-z0-9]{12,}"
    r"|(?<![\w/.-])(?=[A-Za-z0-9_-]*\d)(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z0-9_-]{32,}(?![\w/.-])", re.I)


def scrub(text):
    """The text with every home directory path replaced by HOME_PLACEHOLDER."""
    return HOME_PATH.sub(HOME_PLACEHOLDER, text)


def has_secret(text):
    """True when the text names a credential word or holds a token-like string or an email address."""
    return SECRET_TEXT.search(text) is not None
