"""number_masking.py: compare text that differs only in its numbers. Standard library only."""
import re

NUMBER_RUN = re.compile(r"\d+")
NUMBER_PLACEHOLDER = "#"


def masked_numbers(text):
    """`text` with every run of digits replaced by one `#`, so two lines that differ only in a count, a status code,
    a duration or a timestamp mask to the same text."""
    return NUMBER_RUN.sub(NUMBER_PLACEHOLDER, text)
