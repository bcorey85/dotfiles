-- dredge — personal theme-mode family, dark and light. Prose first, diffs second:
-- cool charcoal ground (OKLCH L 0.265, h 250), fg and greys tinted to the ground hue
-- (C 0.025). Contrast is tuned in APCA Lc, not WCAG ratios, which overrate
-- light-on-dark. Dark is deliberately dim against halation: fg Lc 70 (~9.2:1),
-- comments 47, punctuation 46. Light: fg Lc 88. At Lc 75 on cream the gamut leaves
-- no chroma, and every token reads as black. Lc is a floor, not a target: coloured
-- token pairs also keep OKLab dE >= 0.09 in light, >= 0.085 in dark.
-- The more often a token appears, the calmer its colour. Variables, parameters and
-- named constants are teal (h 194-202). Object keys and member access are blue
-- (h 248), the dimmest role in both modes. Functions and classes are periwinkle
-- (h 280-284). Literals and builtins are rose (h 0; None, numbers, booleans, self,
-- JSON). No green in code. Light mirrors dark's hues and relative weights.
-- Strings are fg. Keywords are the ground's grey, italic, half a step above
-- comments; types share the grey, upright, and so do markup tags. Modules stay fg.
-- Markdown headings are orange.
-- Diffs: added = green signs on a green wash (green is free: code never uses it),
-- removed = red, same washes as hunk. Changed words separate by chroma, not
-- lightness. Red reads louder than green, so the removed wash carries less chroma.
-- Teal is the accent; yellow marks changed. The palette below is the source of truth; the
-- ghostty/herdr/hunk/starship/quickshell/claude-theme copies mirror it by hand.
-- Editing: one value at a time, judged on a real file in nvim and hunk before the
-- mirrors are touched. The Lc/dE numbers rule candidates out; they never pick one.
-- Body text never rises above fg; fg_bright is emphasis only.

local palettes = {}

palettes.dark = {
  bg = "#202427",
  bg_dark = "#1a1d21",
  bg_line = "#282b2e",
  bg_sel = "#30363d",
  bg_visual = "#373d42",
  border = "#3e4248",
  nontext = "#41474c",
  linenr = "#747c83",
  muted = "#95a0ab",
  comment = "#a1aebb",
  punct = "#808c99",
  fg = "#bdc8d3",
  fg_bright = "#d3dbe3",

  red = "#f77972",
  amber = "#ffa475",
  yellow = "#ebc75b",
  green = "#82d395",
  teal = "#79cfcf",
  blue = "#7abff9",
  magenta = "#e091d8",

  kw = "#808c99",
  type_name = "#a1aebb",
  var = "#72cacb",
  fn = "#abb1fd",
  str = "#bdc8d3",
  const = "#e390aa",
  key = "#75afe3",
  type = "#75afe3",
  param = "#72cacb",
  heading = "#d5ac93",

  added = "#82d395",
  diff_add = "#1a2d27",
  diff_delete = "#2a2323",
  diff_change = "#1a2d27",
  diff_text = "#17463b",
  search = "#56442c",

  term = {
    "#1a1d21", "#f77972", "#82d395", "#ebc75b", "#7abff9", "#e091d8", "#79cfcf", "#bdc8d3",
    "#727c86", "#ff9790", "#a6e7b3", "#fdde8c", "#a0d4ff", "#efade8", "#a7e1e0", "#d3dbe3",
  },
}

-- Light: cool light grey (OKLCH L 0.82), greys on dark's hue (h 248). Accents sit
-- light, around L 0.56-0.64; luminance over contrast.
palettes.light = {
  bg = "#bac6d1",
  bg_dark = "#b5c1cd",
  bg_line = "#b1bdc8",
  bg_sel = "#a3b0bc",
  bg_visual = "#a4afca",
  border = "#919da9",
  nontext = "#9aa6b2",
  linenr = "#77828c",
  muted = "#6f7a85",
  comment = "#596571",
  punct = "#697480",
  fg = "#2d3740",
  fg_bright = "#1f252a",

  red = "#ba3535",
  amber = "#bb5d00",
  yellow = "#886100",
  green = "#1d7d3e",
  teal = "#007475",
  blue = "#116bb5",
  magenta = "#993f94",

  kw = "#697480",
  type_name = "#596571",
  var = "#007e82",
  fn = "#5e56c3",
  str = "#2d3740",
  const = "#b94571",
  key = "#0d6db2",
  param = "#007e82",
  heading = "#ba7c4d",
  type = "#0d6db2",

  added = "#1d7d3e",
  diff_add = "#adcbd0",
  diff_delete = "#c4c3cd",
  diff_change = "#adcbd0",
  diff_text = "#95c5c6",
  search = "#d5ac76",

  term = {
    "#2d3740", "#ba3535", "#1d7d3e", "#886100", "#116bb5", "#993f94", "#007475", "#555f69",
    "#535d67", "#d74745", "#2a904b", "#b08505", "#2b7ec9", "#ad51a7", "#008c8d", "#2d3740",
  },
}

local mode = vim.o.background == "light" and "light" or "dark"
local c = palettes[mode]

vim.cmd("highlight clear")
if vim.fn.exists("syntax_on") == 1 then
  vim.cmd("syntax reset")
end
vim.o.background = mode
vim.g.colors_name = "dredge"

local groups = {
  -- editor
  Normal = { fg = c.fg, bg = c.bg },
  NormalNC = { link = "Normal" },
  NormalFloat = { fg = c.fg, bg = c.bg_dark },
  FloatBorder = { fg = c.border, bg = c.bg_dark },
  FloatTitle = { fg = c.teal, bg = c.bg_dark, bold = true },
  Cursor = { fg = c.bg, bg = c.teal },
  CursorLine = { bg = c.bg_line },
  CursorColumn = { link = "CursorLine" },
  ColorColumn = { bg = c.bg_line },
  CursorLineNr = { fg = c.teal, bold = true },
  LineNr = { fg = c.linenr },
  SignColumn = { fg = c.linenr },
  FoldColumn = { fg = c.linenr },
  Folded = { fg = c.comment, bg = c.bg_line },
  WinSeparator = { fg = c.border },
  VertSplit = { link = "WinSeparator" },
  StatusLine = { fg = c.fg, bg = c.bg_dark },
  StatusLineNC = { fg = c.muted, bg = c.bg_dark },
  WinBar = { fg = c.fg, bold = true },
  WinBarNC = { fg = c.muted },
  TabLine = { fg = c.muted, bg = c.bg_dark },
  TabLineFill = { bg = c.bg_dark },
  TabLineSel = { fg = c.fg_bright, bg = c.bg, bold = true },
  Pmenu = { fg = c.fg, bg = c.bg_dark },
  PmenuSel = { bg = c.bg_sel, bold = true },
  PmenuKind = { fg = c.teal, bg = c.bg_dark },
  PmenuExtra = { fg = c.muted, bg = c.bg_dark },
  PmenuSbar = { bg = c.bg_line },
  PmenuThumb = { bg = c.border },
  PmenuMatch = { fg = c.teal, bold = true },
  WildMenu = { link = "PmenuSel" },
  Visual = { bg = c.bg_visual },
  VisualNOS = { link = "Visual" },
  Search = { fg = c.fg_bright, bg = c.search },
  IncSearch = { fg = c.bg, bg = c.fn },
  CurSearch = { link = "IncSearch" },
  Substitute = { fg = c.bg, bg = c.magenta },
  MatchParen = { fg = c.teal, bg = c.bg_visual, bold = true },
  NonText = { fg = c.nontext },
  Whitespace = { fg = c.nontext },
  EndOfBuffer = { fg = c.bg },
  SpecialKey = { fg = c.nontext },
  Conceal = { fg = c.muted },
  Directory = { fg = c.blue },
  Title = { fg = c.teal, bold = true },
  ErrorMsg = { fg = c.red },
  WarningMsg = { fg = c.yellow },
  MoreMsg = { fg = c.green },
  ModeMsg = { fg = c.fg, bold = true },
  Question = { fg = c.blue },
  QuickFixLine = { bg = c.bg_sel },
  SpellBad = { sp = c.red, undercurl = true },
  SpellCap = { sp = c.yellow, undercurl = true },
  SpellLocal = { sp = c.teal, undercurl = true },
  SpellRare = { sp = c.magenta, undercurl = true },

  -- syntax
  Comment = { fg = c.comment, italic = true },
  Constant = { fg = c.const },
  String = { fg = c.str },
  Character = { fg = c.str },
  Number = { fg = c.const },
  Boolean = { fg = c.const },
  Float = { fg = c.const },
  Identifier = { fg = c.var },
  Function = { fg = c.fn },
  Statement = { fg = c.kw, italic = true },
  Conditional = { fg = c.kw, italic = true },
  Repeat = { fg = c.kw, italic = true },
  Label = { fg = c.kw, italic = true },
  Operator = { fg = c.punct },
  Keyword = { fg = c.kw, italic = true },
  Exception = { fg = c.kw, italic = true },
  PreProc = { fg = c.kw, italic = true },
  Include = { fg = c.kw, italic = true },
  Define = { fg = c.kw, italic = true },
  Macro = { fg = c.fn },
  PreCondit = { fg = c.kw, italic = true },
  Type = { fg = c.type_name },
  StorageClass = { fg = c.kw, italic = true },
  Structure = { fg = c.type_name },
  Typedef = { fg = c.type_name },
  Special = { fg = c.const },
  SpecialChar = { fg = c.const },
  Tag = { fg = c.kw },
  Delimiter = { fg = c.punct },
  SpecialComment = { fg = c.comment, italic = true },
  Debug = { fg = c.red },
  Underlined = { underline = true },
  Error = { fg = c.red },
  Todo = { fg = c.bg, bg = c.const, bold = true },

  -- treesitter
  ["@variable"] = { fg = c.var },
  ["@variable.builtin"] = { fg = c.const },
  ["@variable.parameter"] = { fg = c.param },
  ["@variable.member"] = { fg = c.key },
  ["@property"] = { fg = c.key },
  ["@variable.member.key"] = { fg = c.key },
  -- Named constants read as variables; literals and builtins stay c.const.
  ["@constant"] = { fg = c.var },
  ["@constant.builtin"] = { fg = c.const },
  ["@constant.macro"] = { fg = c.param },
  ["@module"] = { fg = c.fg },
  ["@module.builtin"] = { fg = c.fg },
  ["@label"] = { fg = c.kw, italic = true },
  ["@string"] = { fg = c.str },
  ["@string.documentation"] = { fg = c.comment, italic = true },
  ["@string.escape"] = { fg = c.const },
  ["@string.regexp"] = { fg = c.const },
  ["@string.special"] = { fg = c.const },
  ["@string.plain"] = { fg = c.str },
  ["@string.special.url"] = { fg = c.type, underline = true },
  ["@character"] = { fg = c.str },
  ["@character.special"] = { fg = c.const },
  ["@number"] = { fg = c.const },
  ["@boolean"] = { fg = c.const },
  ["@type"] = { fg = c.type_name },
  ["@type.builtin"] = { fg = c.type_name },
  ["@type.definition"] = { fg = c.type_name },  ["@attribute"] = { fg = c.const },
  ["@function"] = { fg = c.fn },
  ["@function.builtin"] = { fg = c.fn },
  ["@function.call"] = { fg = c.fn },
  ["@function.macro"] = { fg = c.fn },
  ["@function.method"] = { fg = c.fn },
  ["@function.method.call"] = { fg = c.fn },
  -- Classes are callables: purple.
  ["@constructor"] = { fg = c.fn },
  -- Python has no pure types; tree-sitter captures capitalised names as @type.
  ["@type.python"] = { fg = c.fn },
  ["@type.definition.python"] = { fg = c.fn },
  -- Lua captures table braces as @constructor.
  ["@constructor.lua"] = { link = "@punctuation.bracket" },
  ["@operator"] = { fg = c.punct },
  ["@keyword"] = { fg = c.kw, italic = true },
  ["@keyword.function"] = { fg = c.kw, italic = true },
  ["@keyword.operator"] = { fg = c.kw, italic = true },
  ["@keyword.import"] = { fg = c.kw, italic = true },
  ["@keyword.return"] = { fg = c.kw, italic = true },
  ["@keyword.exception"] = { fg = c.kw, italic = true },
  ["@keyword.conditional"] = { fg = c.kw, italic = true },
  ["@keyword.repeat"] = { fg = c.kw, italic = true },
  ["@keyword.coroutine"] = { fg = c.kw, italic = true },
  ["@keyword.directive"] = { fg = c.kw, italic = true },
  ["@punctuation.delimiter"] = { fg = c.punct },
  ["@punctuation.bracket"] = { fg = c.punct },
  ["@punctuation.special"] = { fg = c.punct },
  ["@comment"] = { link = "Comment" },
  ["@comment.error"] = { fg = c.red, bold = true },
  ["@comment.warning"] = { fg = c.yellow, bold = true },
  ["@comment.note"] = { fg = c.teal, bold = true },
  ["@comment.todo"] = { link = "Todo" },
  ["@tag"] = { fg = c.kw },
  ["@tag.builtin"] = { fg = c.kw },
  ["@tag.attribute"] = { fg = c.fn },
  ["@tag.delimiter"] = { fg = c.punct },
  ["@markup.strong"] = { bold = true },
  ["@markup.italic"] = { italic = true },
  ["@markup.strikethrough"] = { strikethrough = true },
  ["@markup.underline"] = { underline = true },
  ["@markup.heading"] = { fg = c.heading, bold = true },
  ["@markup.quote"] = { fg = c.comment, italic = true },
  ["@markup.math"] = { fg = c.const },
  ["@markup.link"] = { fg = c.type },
  ["@markup.link.label"] = { fg = c.type },
  ["@markup.link.url"] = { fg = c.type, underline = true },
  ["@markup.raw"] = { fg = c.str },
  ["@markup.list"] = { fg = c.punct },
  ["@markup.list.checked"] = { fg = c.green },
  ["@markup.list.unchecked"] = { fg = c.muted },
  ["@diff.plus"] = { fg = c.added },
  ["@diff.minus"] = { fg = c.red },
  ["@diff.delta"] = { fg = c.yellow },

  -- lsp semantic tokens
  ["@lsp.type.class"] = { link = "@constructor" },
  ["@lsp.type.comment"] = {},
  ["@lsp.type.decorator"] = { link = "@attribute" },
  ["@lsp.type.enum"] = { link = "@type" },
  ["@lsp.type.enumMember"] = { link = "@constant" },
  -- Cleared: LSP marks function-valued variables and properties as functions.
  -- Tree-sitter colours only definitions and calls, the same as hunk.
  ["@lsp.type.function"] = {},
  ["@lsp.type.interface"] = { link = "@type.definition" },
  ["@lsp.type.macro"] = { link = "@function.macro" },
  ["@lsp.type.method"] = {},
  ["@lsp.type.namespace"] = { link = "@module" },
  ["@lsp.type.parameter"] = { link = "@variable.parameter" },
  ["@lsp.type.property"] = { link = "@property" },
  ["@lsp.type.struct"] = { link = "@type.definition" },
  ["@lsp.type.type"] = { link = "@type" },
  ["@lsp.type.typeParameter"] = { link = "@type.definition" },
  ["@lsp.type.variable"] = { link = "@variable" },
  ["@lsp.typemod.variable.defaultLibrary"] = { link = "@variable.builtin" },
  ["@lsp.typemod.function.defaultLibrary"] = { link = "@function.builtin" },
  -- basedpyright marks UPPER_CASE names readonly. Python only: TS marks every const.
  ["@lsp.typemod.variable.readonly.python"] = { link = "@constant" },
  LspReferenceText = { bg = c.bg_sel },
  LspReferenceRead = { bg = c.bg_sel },
  LspReferenceWrite = { bg = c.bg_sel, bold = true },
  LspInlayHint = { fg = c.muted, bg = c.bg_line },
  LspSignatureActiveParameter = { fg = c.teal, bold = true },

  -- diagnostics
  DiagnosticError = { fg = c.red },
  DiagnosticWarn = { fg = c.yellow },
  DiagnosticInfo = { fg = c.blue },
  DiagnosticHint = { fg = c.teal },
  DiagnosticOk = { fg = c.green },
  DiagnosticUnderlineError = { sp = c.red, undercurl = true },
  DiagnosticUnderlineWarn = { sp = c.yellow, undercurl = true },
  DiagnosticUnderlineInfo = { sp = c.blue, undercurl = true },
  DiagnosticUnderlineHint = { sp = c.teal, undercurl = true },
  DiagnosticUnderlineOk = { sp = c.green, undercurl = true },
  DiagnosticUnnecessary = { fg = c.muted },
  DiagnosticDeprecated = { strikethrough = true },

  -- diff / git
  DiffAdd = { bg = c.diff_add },
  DiffDelete = { bg = c.diff_delete },
  DiffChange = { bg = c.diff_change },
  DiffText = { bg = c.diff_text },
  Added = { fg = c.added },
  Changed = { fg = c.yellow },
  Removed = { fg = c.red },
  diffAdded = { fg = c.added },
  diffRemoved = { fg = c.red },
  diffChanged = { fg = c.yellow },
  diffFile = { fg = c.type },
  diffLine = { fg = c.muted },
  GitSignsAdd = { fg = c.added },
  GitSignsChange = { fg = c.yellow },
  GitSignsDelete = { fg = c.red },
  -- Inline overlay shows the old line in rose above, so changed lines take the
  -- added wash.
  GitSignsChangeLn = { link = "DiffAdd" },

  -- plugins
  SnacksPickerDir = { fg = c.comment },
  MiniClueDescGroup = { fg = c.teal },
  MiniClueSeparator = { fg = c.border },
  MiniIndentscopeSymbol = { fg = c.linenr },
}

for name, spec in pairs(groups) do
  vim.api.nvim_set_hl(0, name, spec)
end

for i, color in ipairs(c.term) do
  vim.g["terminal_color_" .. (i - 1)] = color
end

-- Assignment target directly in a Python class body (class attribute definition).
local function class_attr_def(buf, line, col)
  local ok, node = pcall(vim.treesitter.get_node, { bufnr = buf, pos = { line, col } })
  if not ok or not node or node:type() ~= "identifier" then
    return false
  end
  local assign = node:parent()
  local stmt = assign and assign:parent()
  local block = stmt and stmt:parent()
  local class = block and block:parent()
  return assign:type() == "assignment"
    and assign:field("left")[1] == node
    and stmt:type() == "expression_statement"
    and class ~= nil
    and class:type() == "class_definition"
end

-- Key of an object literal or object type at its definition.
local function object_key_def(buf, line, col)
  local ok, node = pcall(vim.treesitter.get_node, { bufnr = buf, pos = { line, col } })
  if not ok or not node then
    return false
  end
  if node:type() == "shorthand_property_identifier" then
    return true
  elseif node:type() ~= "property_identifier" then
    return false
  end
  local parent = node:parent()
  return (parent:type() == "pair" and parent:field("key")[1] == node)
    or (parent:type() == "property_signature" and parent:field("name")[1] == node)
end

-- Keyword-argument name at a Python call site.
local function kwarg_name(buf, line, col)
  local ok, node = pcall(vim.treesitter.get_node, { bufnr = buf, pos = { line, col } })
  if not ok or not node or node:type() ~= "identifier" then
    return false
  end
  local parent = node:parent()
  return parent:type() == "keyword_argument" and parent:field("name")[1] == node
end

-- Tree-sitter parses a value name as `identifier` and a type name as `type_identifier`.
local function value_name(buf, line, col)
  local ok, node = pcall(vim.treesitter.get_node, { bufnr = buf, pos = { line, col } })
  return ok and node ~= nil and node:type() == "identifier"
end

-- LSP marks UPPER_CASE class attributes as properties and TS consts as variables.
-- An all-caps name is a named constant in every language, so colour it as one.
-- A class attribute at its definition takes the member colour of its accesses.
-- A keyword-argument name takes the keyword grey, not the parameter teal.
-- Library globals (JSON) stay builtins.
-- tsserver tags every use of a name that is both a const and a type as a type;
-- its value uses take the variable colour.
vim.api.nvim_create_autocmd("LspTokenUpdate", {
  group = vim.api.nvim_create_augroup("dredge_constants", { clear = true }),
  callback = function(ev)
    local t = ev.data.token
    if vim.g.colors_name ~= "dredge" then
      return
    end
    if t.type == "type" then
      if value_name(ev.buf, t.line, t.start_col) then
        vim.lsp.semantic_tokens.highlight_token(t, ev.buf, ev.data.client_id, "@variable")
      end
      return
    elseif t.type == "parameter" then
      if kwarg_name(ev.buf, t.line, t.start_col) then
        vim.lsp.semantic_tokens.highlight_token(t, ev.buf, ev.data.client_id, "@variable.member.key.python")
      end
      return
    elseif t.type ~= "variable" and t.type ~= "property" then
      return
    elseif t.modifiers.defaultLibrary then
      return
    end
    local text = vim.api.nvim_buf_get_text(ev.buf, t.line, t.start_col, t.line, t.end_col, {})[1]
    if text and text:match("^_*%u[%u%d_]+$") then
      vim.lsp.semantic_tokens.highlight_token(t, ev.buf, ev.data.client_id, "@constant")
    elseif class_attr_def(ev.buf, t.line, t.start_col) then
      vim.lsp.semantic_tokens.highlight_token(t, ev.buf, ev.data.client_id, "@variable.member")
    elseif object_key_def(ev.buf, t.line, t.start_col) then
      vim.lsp.semantic_tokens.highlight_token(t, ev.buf, ev.data.client_id, "@variable.member.key")
    end
  end,
})
