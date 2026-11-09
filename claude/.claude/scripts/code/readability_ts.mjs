// Helper for readability_check.py. stdin: {"tsdir": "<typescript package dir>", "files": ["<path>", ...]}.
// stdout: {"<path>": [{"name": name, "s": startLine, "e": endLine, "deep": [line, ...], "nest": [[line, depth], ...],
// "ternary": [line, ...], "argternary": [line, ...], "comp": [], "wide": [[line, count], ...],
// "params": [line, count]}] | null}. null means the file did not parse cleanly. Every function-like node is one record;
// a nested function is its own record. "nest" lists each control statement deeper than MAX_NESTING in its function;
// an else-if stays at its if's level. A .vue file is read as its <script> blocks with every other character blanked,
// so line numbers stay the .vue file's; a .vue file with no <script> block has no records.
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import path from "node:path";

const MAX_NESTING = 2;
const MIN_WIDE_TUPLE = 3;
const input = JSON.parse(readFileSync(0, "utf8"));
const ts = createRequire(import.meta.url)(input.tsdir);
const K = ts.SyntaxKind;

const FUNCTIONS = new Set([K.FunctionDeclaration, K.FunctionExpression, K.ArrowFunction, K.MethodDeclaration,
  K.Constructor, K.GetAccessor, K.SetAccessor]);
const CLASSES = new Set([K.ClassDeclaration, K.ClassExpression]);
const CONTROL = new Set([K.IfStatement, K.ForStatement, K.ForOfStatement, K.ForInStatement, K.WhileStatement,
  K.DoStatement, K.SwitchStatement, K.TryStatement]);
const TRANSPARENT = new Set([K.SpreadElement, K.AwaitExpression, K.PrefixUnaryExpression, K.PostfixUnaryExpression,
  K.TypeOfExpression, K.VoidExpression, K.DeleteExpression, K.ParenthesizedExpression, K.AsExpression,
  K.NonNullExpression, K.SatisfiesExpression, K.TypeAssertionExpression, K.TemplateExpression, K.TemplateSpan]);
const VUE_SCRIPT = /<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi;
const VUE_LANG = /\blang\s*=\s*["']?(\w+)/i;
const VUE_KINDS = { ts: ts.ScriptKind.TS, tsx: ts.ScriptKind.TSX, jsx: ts.ScriptKind.JSX };

function scriptKind(file) {
  switch (path.extname(file)) {
    case ".tsx": return ts.ScriptKind.TSX;
    case ".jsx": return ts.ScriptKind.JSX;
    case ".js": case ".mjs": case ".cjs": return ts.ScriptKind.JS;
    default: return ts.ScriptKind.TS;
  }
}

function blank(text) {
  return text.replace(/[^\r\n]/g, " ");
}

// {text, kind} of a .vue file's <script> blocks at their own lines, or null when it has none. TS when any block is
// lang="ts" (or tsx/jsx), else JS.
function vueScript(text) {
  const blocks = [...text.matchAll(VUE_SCRIPT)];
  if (blocks.length === 0) return null;
  let kind = ts.ScriptKind.JS;
  let source = "";
  let last = 0;
  for (const block of blocks) {
    const bodyStart = block.index + block[0].indexOf(">") + 1;
    source += blank(text.slice(last, bodyStart)) + block[2];
    last = bodyStart + block[2].length;
    const lang = VUE_LANG.exec(block[1])?.[1].toLowerCase();
    if (VUE_KINDS[lang] !== undefined) kind = VUE_KINDS[lang];
  }
  return { text: source + blank(text.slice(last)), kind };
}

function unwrap(node) {
  let inner = node;
  while (inner.kind === K.ParenthesizedExpression) inner = inner.expression;
  return inner;
}

function isChainedTernary(node) {
  const parts = [node.condition, node.whenTrue, node.whenFalse];
  return parts.some((part) => unwrap(part).kind === K.ConditionalExpression);
}

function isElseIf(node) {
  return node.kind === K.IfStatement && node.parent.kind === K.IfStatement && node.parent.elseStatement === node;
}

function functionName(node) {
  if (node.name) return node.name.getText();
  if (node.kind === K.Constructor) return "constructor";
  const parent = node.parent;
  if (parent && (parent.kind === K.VariableDeclaration || parent.kind === K.PropertyAssignment) && parent.name) {
    return parent.name.getText();
  }
  return "<anonymous>";
}

// The element count of a returned array literal that reads as a tuple: MIN_WIDE_TUPLE or more values, in a function
// with a tuple return type or none. 0 otherwise.
function wideTupleCount(expression, fn) {
  if (!expression) return 0;
  const returned = unwrap(expression);
  if (returned.kind !== K.ArrayLiteralExpression) return 0;
  const readsAsTuple = !fn.type || fn.type.kind === K.TupleType;
  const count = returned.elements.length;
  return readsAsTuple && count >= MIN_WIDE_TUPLE ? count : 0;
}

function readSource(file) {
  const text = readFileSync(file, "utf8");
  if (path.extname(file) !== ".vue") return { text, kind: scriptKind(file) };
  return vueScript(text);
}

function analyze(file) {
  const source = readSource(file);
  if (!source) return [];
  const sf = ts.createSourceFile(file, source.text, ts.ScriptTarget.Latest, true, source.kind);
  if (sf.parseDiagnostics.length > 0) return null;

  const lineOf = (pos) => sf.getLineAndCharacterOfPosition(pos).line + 1;
  const records = [];
  const depthOf = new Map();
  const functionOf = new Map();

  function recordWide(expression, rec) {
    const count = wideTupleCount(expression, functionOf.get(rec));
    if (count) rec.wide.push([lineOf(expression.getStart(sf)), count]);
  }

  function visitFunction(node, rec) {
    for (const param of node.parameters ?? []) visit(param, 0, rec);
    if (!node.body) return;
    const params = node.parameters.filter((param) => param.name.getText() !== "this");
    const own = { name: functionName(node), s: lineOf(node.getStart(sf)), e: lineOf(node.getEnd()), deep: [],
      nest: [], ternary: [], argternary: [], comp: [], wide: [], params: [lineOf(node.parameters.pos), params.length] };
    records.push(own);
    depthOf.set(own, 0);
    functionOf.set(own, node);
    if (node.body.kind !== K.Block) recordWide(node.body, own);
    visit(node.body, 0, own);
  }

  function visitControl(node, rec) {
    const depth = depthOf.get(rec) + 1;
    if (depth > MAX_NESTING) rec.nest.push([lineOf(node.getStart(sf)), depth]);
    depthOf.set(rec, depth);
    ts.forEachChild(node, (child) => visit(child, 0, rec));
    depthOf.set(rec, depth - 1);
  }

  function visitCall(node, level, rec) {
    if (level >= 2) rec.deep.push(lineOf(node.getStart(sf)));
    visit(node.expression, 0, rec);
    for (const arg of node.arguments ?? []) {
      if (unwrap(arg).kind === K.ConditionalExpression) rec.argternary.push(lineOf(arg.getStart(sf)));
      visit(arg, level + 1, rec);
    }
  }

  function visit(node, level, rec) {
    if (FUNCTIONS.has(node.kind)) return visitFunction(node, rec);
    if (CLASSES.has(node.kind)) return ts.forEachChild(node, (child) => visit(child, 0, null));
    if (!rec) return ts.forEachChild(node, (child) => visit(child, 0, null));
    if (CONTROL.has(node.kind) && !isElseIf(node)) return visitControl(node, rec);
    if (node.kind === K.CallExpression || node.kind === K.NewExpression) return visitCall(node, level, rec);
    if (node.kind === K.ConditionalExpression && isChainedTernary(node)) rec.ternary.push(lineOf(node.getStart(sf)));
    if (node.kind === K.ReturnStatement) recordWide(node.expression, rec);

    const passed = TRANSPARENT.has(node.kind) ? level : 0;
    ts.forEachChild(node, (child) => visit(child, passed, rec));
  }

  visit(sf, 0, null);
  return records;
}

const out = {};
for (const file of input.files) {
  try { out[file] = analyze(file); } catch { out[file] = null; }
}
process.stdout.write(JSON.stringify(out));
