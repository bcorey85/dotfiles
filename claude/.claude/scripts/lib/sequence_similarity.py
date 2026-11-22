"""How close two sequences of hashable items are: a bounded edit distance and a multiset overlap ratio.

Plain functions over any two sequences (token lists, words, ids); no module rule, standard library only.
For two strings compared character by character, use `script_utils.text_similarity`."""
from collections import Counter


def edit_distance_within(first, second, limit):
    """The Levenshtein distance between two sequences when it is at most `limit`, else None.

    Only the band of cells within `limit` of the diagonal is filled, so the cost is len(first) * (2 * limit + 1)."""
    if abs(len(first) - len(second)) > limit:
        return None
    if len(first) > len(second):
        first, second = second, first

    beyond = limit + 1
    previous = [min(column, beyond) for column in range(len(second) + 1)]
    for row, item in enumerate(first, start=1):
        current = [beyond] * (len(second) + 1)
        current[0] = min(row, beyond)
        band_start = max(1, row - limit)
        band_end = min(len(second), row + limit)
        for column in range(band_start, band_end + 1):
            substitution = previous[column - 1] + (item != second[column - 1])
            current[column] = min(substitution, previous[column] + 1, current[column - 1] + 1, beyond)
        if min(current) > limit:
            return None
        previous = current
    distance = previous[len(second)]
    if distance > limit:
        return None
    return distance


def ngram_counts(sequence, size):
    """Counter of each run of `size` neighbouring items, so a multiset comparison sees order as well as content."""
    runs = zip(*(sequence[offset:] for offset in range(size)), strict=False)
    return Counter(runs)


def multiset_similarity(first_counts, second_counts):
    """2 * shared / total over two Counters of items: 1.0 for the same items in any order, 0.0 for none shared."""
    total = sum(first_counts.values()) + sum(second_counts.values())
    if total == 0:
        return 1.0
    shared = sum((first_counts & second_counts).values())
    return 2 * shared / total
