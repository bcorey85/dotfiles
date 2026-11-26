"""Shape clones for /refactor branch-prep: compare function bodies with names, attribute names and literals
stripped, which jscpd's token runs miss.

Two lists for the smell-reviewer, no model call:
- candidate pairs: a function the branch changed against every function in the repo. The same normalized body is a
  renamed copy; a body a few tokens away (`<` against `<=`, one extra guard) is a near match.
- a catalog: for each function the branch added, the nearest other functions. The smell-reviewer judges whether
  one already does the job or the added function is a generic operation under a domain name.

Python bodies are read with `ast`. TypeScript and TSX bodies are read from the `tree-sitter parse --xml` output of
the grammar nvim installed; a missing CLI or grammar is a note, not a stop.
"""
import ast
import sys
import warnings
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "lib"))
import clone_pairs
import script_utils
import sequence_similarity
import source_paths
import tree_sitter_xml

MIN_BODY_TOKENS = 16
# A near match is within one token edit per this many tokens, and at least one edit.
TOKENS_PER_EDIT = 20
MAX_SHAPE_PAIRS = 30
MAX_CATALOG_FUNCTIONS = 12
MAX_NEIGHBOURS = 3
NEIGHBOUR_FLOOR = 0.65
NGRAM_SIZE = 2
SHAPE_WIDTH = 12
# (suffix, grammar file, tree-sitter language name)
TYPESCRIPT_GRAMMARS = ((".tsx", "tsx", "tsx"), (".ts", "typescript", "typescript"))

ID_TOKEN = "ID"
ATTRIBUTE_TOKEN = "ATTR"
LITERAL_TOKEN = "LIT"
LIST_END_TOKEN = "END"
TS_PLACEHOLDERS = {
    "identifier": ID_TOKEN, "shorthand_property_identifier": ID_TOKEN,
    "shorthand_property_identifier_pattern": ID_TOKEN, "statement_identifier": ID_TOKEN,
    "property_identifier": ATTRIBUTE_TOKEN, "private_property_identifier": ATTRIBUTE_TOKEN,
    "type_identifier": ID_TOKEN, "jsx_text": LITERAL_TOKEN,
    "string": LITERAL_TOKEN, "number": LITERAL_TOKEN, "template_string": LITERAL_TOKEN, "regex": LITERAL_TOKEN,
    "true": LITERAL_TOKEN, "false": LITERAL_TOKEN, "null": LITERAL_TOKEN, "undefined": LITERAL_TOKEN,
}
TS_DROPPED_TAGS = {"comment", "type_annotation", "type_arguments", "type_parameters"}
TS_FUNCTION_TAGS = {"function_declaration", "generator_function_declaration", "method_definition", "arrow_function",
                    "function_expression", "generator_function"}
PY_DROPPED_FIELDS = {"annotation", "returns", "type_comment"}


class FunctionShape(NamedTuple):
    path: str
    name: str
    signature: str
    first_line: int
    last_line: int
    tokens: tuple


class ShapePair(NamedTuple):
    changed: FunctionShape
    other: FunctionShape
    distance: int  # 0 is a renamed copy


class CatalogListing(NamedTuple):
    added: FunctionShape
    neighbours: list  # (FunctionShape, similarity), closest first


class ShapeResult(NamedTuple):
    pairs: list  # ShapePair
    listings: list  # CatalogListing
    notes: list  # strings: what was not read
    skipped: str = ""  # why the whole pass did not run
    uncataloged: int = 0  # added functions past MAX_CATALOG_FUNCTIONS that got no nearest-helper listing
    repo_unread: bool = False  # git could not list the repo's files, so no function was read


class FunctionsRead(NamedTuple):
    shapes: list  # FunctionShape
    notes: list  # strings: what was not read
    repo_unread: bool = False  # git could not list the repo's files


def skipped_result(reason):
    return ShapeResult([], [], [], reason)


# ------------------------------------------------------------------ Python

def _ast_children(value):
    if isinstance(value, ast.AST):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, ast.AST)]
    return []


def _walk_python(node, tokens):
    if isinstance(node, ast.expr_context):
        return
    tokens.append(type(node).__name__)
    for field, value in ast.iter_fields(node):
        if field in PY_DROPPED_FIELDS:
            continue
        children = _ast_children(value)
        for child in children:
            _walk_python(child, tokens)
        # The end marker keeps a statement moved out of a block, or an argument moved out of a nested call,
        # from reading as the same token run.
        if isinstance(value, list) and children:
            tokens.append(LIST_END_TOKEN)


def python_body_tokens(function_node):
    """Node class names of the arguments and body: a name, an attribute name and a constant each reduce to their
    node class, an operator keeps its own class. The docstring and every annotation are left out."""
    tokens = []
    _walk_python(function_node.args, tokens)
    body = function_node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    for statement in body:
        _walk_python(statement, tokens)
    return tuple(tokens)


def python_functions(path, source_bytes):
    """The FunctionShape of every def in the file; raises SyntaxError or ValueError on a file that does not parse."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tree = ast.parse(source_bytes)
    shapes = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        signature = f"{node.name}({ast.unparse(node.args)})"
        shapes.append(FunctionShape(path, node.name, signature, node.lineno, node.end_lineno,
                                    python_body_tokens(node)))
    return shapes


# -------------------------------------------------------------- TypeScript

def _emit_ts(element, tokens):
    tag = element.tag
    if tag in TS_DROPPED_TAGS:
        return
    placeholder = TS_PLACEHOLDERS.get(tag)
    if placeholder:
        tokens.append(placeholder)
        return
    if len(element) == 0:
        words = (element.text or "").split()
        tokens.extend(words or [tag])
        return
    tokens.extend((element.text or "").split())
    for child in element:
        _emit_ts(child, tokens)
        tokens.extend((child.tail or "").split())


def ts_body_tokens(function_element):
    """Keyword, operator and punctuation tokens of the function with identifiers, property names and literals
    replaced by placeholders. The function's own name, comments and type annotations are left out."""
    tokens = list((function_element.text or "").split())
    for child in function_element:
        if child.get("field") != "name":
            _emit_ts(child, tokens)
        tokens.extend((child.tail or "").split())
    return tuple(tokens)


def ts_function_name(element, parent):
    """The declared name: the function's own `name`, or the name a variable, field or object key gives an arrow or
    function expression. None for an anonymous function."""
    own = tree_sitter_xml.field_child(element, "name")
    if own is None and parent is not None:
        own = tree_sitter_xml.field_child(parent, "name", "key")
    if own is None:
        return None
    return (own.text or "").strip() or None


def ts_signature(name, element, lines):
    parameters = tree_sitter_xml.field_child(element, "parameters", "parameter")
    if parameters is None:
        return f"{name}()"
    text = tree_sitter_xml.node_source_text(lines, parameters)
    if parameters.get("field") == "parameter":
        text = f"({text})"
    return f"{name}{text}"


def ts_functions(path, source_element, lines):
    """The FunctionShape of every named function, method and arrow function in one `<source>` element."""
    shapes = []
    stack = [(child, source_element) for child in source_element]
    while stack:
        element, parent = stack.pop()
        stack.extend((child, element) for child in element)
        if element.tag not in TS_FUNCTION_TAGS:
            continue
        name = ts_function_name(element, parent)
        if name is None:
            continue
        signature = ts_signature(name, element, lines)
        first_line = int(element.get("srow")) + 1
        last_line = int(element.get("erow")) + 1
        shapes.append(FunctionShape(path, name, signature, first_line, last_line, ts_body_tokens(element)))
    return shapes


def read_typescript(root_dir, paths, suffix, grammar, language):
    """(shapes, notes) for the repo files with `suffix`, parsed with one tree-sitter run."""
    command = tree_sitter_xml.tree_sitter_command()
    if not command:
        return [], ["TypeScript functions not read: tree-sitter CLI not found"]
    grammar_file = tree_sitter_xml.parser_dir() / f"{grammar}.so"
    if not grammar_file.is_file():
        return [], [f"{suffix} functions not read: grammar {grammar_file} not found"]

    absolute = {str(Path(root_dir) / path): path for path in paths}
    xml_root, note = tree_sitter_xml.run_tree_sitter(command, grammar_file, language, list(absolute))
    if note:
        return [], [note]
    shapes = []
    for source in xml_root:
        path = absolute.get(source.get("name"))
        if path is None:
            unexpected = tree_sitter_xml.tree_sitter_not_parsed_note(f"unexpected source name {source.get('name')!r}")
            return [], [unexpected]
        lines = (Path(root_dir) / path).read_bytes().split(b"\n")
        shapes.extend(ts_functions(path, source, lines))
    return shapes, []


# --------------------------------------------------------------- the repo

def read_python_files(root_dir, paths):
    """(shapes, notes); a file that is unreadable or does not parse is counted in a note."""
    shapes = []
    skipped = []
    for path in paths:
        try:
            source_bytes = (Path(root_dir) / path).read_bytes()
            shapes.extend(python_functions(path, source_bytes))
        except (OSError, SyntaxError, ValueError):
            skipped.append(path)
    if not skipped:
        return shapes, []
    return shapes, [f"{len(skipped)} Python file(s) not read (unreadable or not valid Python), first: {skipped[0]}"]


def read_functions(root_dir):
    """FunctionsRead for every Python and TypeScript file git lists in the repo at root_dir."""
    paths = script_utils.repo_file_paths(root_dir)
    if paths is None:
        return FunctionsRead([], [f"git could not list the files in {root_dir}"], repo_unread=True)
    # A tracked file deleted in the work tree is still listed; tree-sitter stops on a missing path.
    paths = [path for path in paths if (Path(root_dir) / path).is_file()]
    shapes, notes = read_python_files(root_dir, [path for path in paths if path.endswith(".py")])
    for suffix, grammar, language in TYPESCRIPT_GRAMMARS:
        suffix_paths = [path for path in paths if path.endswith(suffix) and not path.endswith(".d.ts")]
        if not suffix_paths:
            continue
        typescript_shapes, typescript_notes = read_typescript(root_dir, suffix_paths, suffix, grammar, language)
        shapes.extend(typescript_shapes)
        notes.extend(typescript_notes)
    return FunctionsRead(shapes, notes)


# ------------------------------------------------------------- comparison

def same_place(first, second):
    """Whether the two functions are one function or nested in each other."""
    if first.path != second.path:
        return False
    return first.first_line <= second.last_line and second.first_line <= first.last_line


def is_comparable(function):
    return len(function.tokens) >= MIN_BODY_TOKENS


def function_key(function):
    return (function.path, function.first_line)


def pair_key(first, second):
    return frozenset([function_key(first), function_key(second)])


def _is_pairable(changed, other, seen):
    if same_place(changed, other) or pair_key(changed, other) in seen:
        return False
    return not (source_paths.is_test_path(changed.path) and source_paths.is_test_path(other.path))


def _pairs_of(changed, by_length, seen):
    """The ShapePairs of one changed function; adds each pair's key to `seen`."""
    length = len(changed.tokens)
    limit = max(1, length // TOKENS_PER_EDIT)
    pairs = []
    for other_length in range(length - limit, length + limit + 1):
        for other in by_length.get(other_length, ()):
            if not _is_pairable(changed, other, seen):
                continue
            distance = sequence_similarity.edit_distance_within(changed.tokens, other.tokens, limit)
            if distance is None:
                continue
            seen.add(pair_key(changed, other))
            pairs.append(ShapePair(changed, other, distance))
    return pairs


def find_pairs(changed_functions, functions):
    """ShapePairs of each changed function against the repo's functions: same tokens, or within one token edit per
    TOKENS_PER_EDIT tokens. Two test files pair with nothing: parallel test setup is incidental similarity."""
    by_length = {}
    for function in functions:
        if is_comparable(function):
            by_length.setdefault(len(function.tokens), []).append(function)

    pairs = []
    seen = set()
    for changed in changed_functions:
        if is_comparable(changed):
            pairs.extend(_pairs_of(changed, by_length, seen))
    return sorted(pairs, key=lambda pair: (pair.distance, pair.changed.path, pair.changed.first_line,
                                           pair.other.path, pair.other.first_line))


def nearest_helpers(added, counts_by_function):
    """(FunctionShape, similarity) of the closest catalog entries to `added`, closest first."""
    added_counts = sequence_similarity.ngram_counts(added.tokens, NGRAM_SIZE)
    scored = []
    for other, other_counts in counts_by_function:
        if same_place(added, other):
            continue
        score = sequence_similarity.multiset_similarity(added_counts, other_counts)
        if score >= NEIGHBOUR_FLOOR:
            scored.append((other, score))
    scored.sort(key=lambda entry: (-entry[1], entry[0].path, entry[0].first_line))
    return scored[:MAX_NEIGHBOURS]


def catalog_listings(added_functions, functions, branch_added_keys):
    """A CatalogListing for each added function (all comparable) that has a neighbour among the non-test
    functions of the repo that the branch did not add (`branch_added_keys` holds the (path, first line)
    of each function it added, every line of it)."""
    catalog = [(function, sequence_similarity.ngram_counts(function.tokens, NGRAM_SIZE)) for function in functions
               if is_comparable(function) and not source_paths.is_test_path(function.path)
               and function_key(function) not in branch_added_keys]
    listings = []
    for added in added_functions:
        neighbours = nearest_helpers(added, catalog)
        if neighbours:
            listings.append(CatalogListing(added, neighbours))
    return listings


def branch_shapes(diff_files, untracked, root_dir):
    """The ShapeResult for the work tree at root_dir: pairs for each function that overlaps a changed line, and the
    catalog neighbours of each function whose every line the branch added."""
    changed = clone_pairs.changed_line_sets(diff_files, untracked)
    functions, notes, repo_unread = read_functions(root_dir)
    changed_functions = []
    added_functions = []
    for function in functions:
        site = clone_pairs.CloneSite(function.path, function.first_line, function.last_line)
        if not clone_pairs.site_touches(site, changed):
            continue
        changed_functions.append(function)
        function_lines = range(function.first_line, function.last_line + 1)
        if all(line in changed[function.path] for line in function_lines):
            added_functions.append(function)

    pairs = find_pairs(changed_functions, functions)
    added_keys = {function_key(function) for function in added_functions}
    # A function under the token floor can never get a listing, so it takes no place under the cap.
    # A test function is never in the catalog's neighbours, so it takes no place either.
    listable = sorted((function for function in added_functions
                       if is_comparable(function) and not source_paths.is_test_path(function.path)),
                      key=function_key)
    listings = catalog_listings(listable[:MAX_CATALOG_FUNCTIONS], functions, added_keys)
    uncataloged = max(0, len(listable) - MAX_CATALOG_FUNCTIONS)
    return ShapeResult(pairs, listings, notes, uncataloged=uncataloged, repo_unread=repo_unread)


# ------------------------------------------------------------------ output

def shape_text(function):
    words = list(function.tokens[:SHAPE_WIDTH])
    if len(function.tokens) > SHAPE_WIDTH:
        words.append("...")
    return " ".join(words)


def site_text(function):
    return f"{function.path}:{function.first_line}-{function.last_line} {function.signature}"


def uncataloged_text(count):
    return f"{count} added function(s) past the first {MAX_CATALOG_FUNCTIONS} not cataloged"


def shape_summary_line(result):
    """The one summary line for the branch-prep header."""
    if result.skipped:
        return f"- shape clones: {result.skipped}"
    notes = "".join(f"; {note}" for note in result.notes)
    if result.uncataloged:
        notes += f"; {uncataloged_text(result.uncataloged)}"
    if not result.pairs and not result.listings:
        return f"- no renamed-copy or near-match pair on changed functions{notes}"
    renamed = sum(1 for pair in result.pairs if pair.distance == 0)
    near = len(result.pairs) - renamed
    listed = len(result.pairs[:MAX_SHAPE_PAIRS])
    return (f"- {renamed} renamed-copy and {near} near-match pair(s) on changed functions ({listed} listed), "
            f"{len(result.listings)} added function(s) with nearest other functions, "
            f"in the dispatch prompt below{notes}")


def pair_section(pairs, title, kind_text):
    lines = [title]
    for pair in pairs:
        lines.append(f"- {site_text(pair.changed)} ~ {site_text(pair.other)}{kind_text(pair)}")
    return lines


def catalog_lines(result):
    """The lines that list the nearest other functions of each added function; empty when there are none."""
    lines = []
    if result.listings:
        lines.append("Nearest other functions for each function this change added:")
    for listing in result.listings:
        lines.append(f"- {site_text(listing.added)} shape: {shape_text(listing.added)}")
        for neighbour, score in listing.neighbours:
            lines.append(f"    - {site_text(neighbour)} [similarity {score:.2f}] shape: {shape_text(neighbour)}")
    if result.uncataloged:
        lines.append(uncataloged_text(result.uncataloged))
    return lines


def print_candidates(result):
    """Print the pair lists and the catalog neighbours; nothing when there is nothing to judge."""
    if not result.pairs and not result.listings:
        return
    listed = result.pairs[:MAX_SHAPE_PAIRS]
    renamed = [pair for pair in listed if pair.distance == 0]
    near = [pair for pair in listed if pair.distance > 0]
    lines = ["Candidate shape clones (function bodies compared with names, attribute names and literals stripped):"]
    if renamed:
        lines += pair_section(renamed, "Renamed copy (same normalized body):", lambda pair: "")
    if near:
        lines += pair_section(near, "Near match (token edits apart):", lambda pair: f" [{pair.distance} edit(s)]")
    if len(result.pairs) > len(listed):
        lines.append(f"{len(result.pairs) - len(listed)} more pair(s) not listed")
    lines += catalog_lines(result)
    print("\n".join(lines))
