-- dredge — personal theme-mode family, dark and light. Prose first, diffs second:
-- cool charcoal ground (OKLCH L 0.232, h 240), fg and greys tinted to the ground hue
-- (C 0.025). Contrast is tuned in APCA Lc, not WCAG ratios, which overrate
-- light-on-dark. Dark is deliberately dim against halation: fg Lc 75,
-- comments 49, punctuation 43. Light: fg Lc 64. Lc is a floor, not a target: coloured
-- token pairs also keep OKLab dE >= 0.09 in light, >= 0.085 in dark.
-- Colour marks definitions; uses and calls are fg. Every definition is
-- periwinkle (h 280-284): top-level variables and constants, functions and
-- classes. Keys, fields, attributes, parameters and builtins (self, JSON) are
-- fg. Literals are rose (h 0; None, numbers, booleans). Strings are
-- teal (h 190-196); comments are blue (h 240). No italics: hunk can't render
-- them, and the two must match.
-- Light mirrors dark's hues. Its code accents (not comments) keep OKLab
-- dE >= 0.25 from the near-black fg, or thin strokes read as black; teal is
-- chroma-capped in sRGB, so it gets there by lightness. Keywords are
-- the ground's grey, and so are markup tags. Types are fg.
-- Modules stay fg. Markdown headings are periwinkle, like definitions.
-- Diffs: added = green signs on a green wash (green is free: code never uses it),
-- removed = orange-red (h 44) on sign, rail and wash alike, clear of the rose
-- literals and the yellow change sign; same washes as hunk. Changed words
-- separate by chroma, not lightness. Red reads louder than green, so the
-- removed wash carries less chroma.
-- Teal is the accent; yellow marks changed. The palette below is the source of truth; the
-- ghostty/herdr/hunk/starship/quickshell/claude-theme copies mirror it by hand.
-- Editing: one value at a time, judged on a real file in nvim and hunk before the
-- mirrors are touched. The Lc/dE numbers rule candidates out; they never pick one.
-- Body text never rises above fg; fg_bright is emphasis only.

local palettes = {}

palettes.dark = {
  bg = "#1a1e21",
  bg_dark = "#14171b",
  bg_line = "#282b2e",
  bg_sel = "#30363d",
  bg_visual = "#373d42",
  border = "#3e4248",
  nontext = "#41474c",
  linenr = "#747c83",
  muted = "#95a0ab",
  comment = "#a1aebb",
  punct = "#8995a2",
  fg = "#c3cfda",
  fg_bright = "#d3dbe3",

  red = "#f77972",
  amber = "#ffa475",
  yellow = "#ebc75b",
  green = "#82d395",
  teal = "#79cfcf",
  blue = "#7abff9",
  magenta = "#e091d8",

  kw = "#8995a2",
  fn = "#adb3f3",
  remark = "#6fa5cb",
  str = "#7fc8c8",
  const = "#dc95aa",

  added = "#82d395",
  removed = "#f97b40",
  diff_add = "#1f2a21",
  diff_delete = "#2f2420",
  diff_change = "#1f2a21",
  diff_text = "#25442c",
  search = "#284f4f",

  term = {
    "#14171b", "#f77972", "#82d395", "#ebc75b", "#7abff9", "#e091d8", "#79cfcf", "#c3cfda",
    "#727c86", "#ff9790", "#a6e7b3", "#fdde8c", "#a0d4ff", "#efade8", "#a7e1e0", "#d3dbe3",
  },
}

-- Light: near-neutral light grey (OKLCH L 0.82, C 0.007), greys on dark's hue
-- (h 248). Accents sit around L 0.47-0.52; luminance over contrast.
palettes.light = {
  bg = "#c1c5c9",
  bg_dark = "#bcc0c4",
  bg_line = "#b8bcc0",
  bg_sel = "#aaafb3",
  bg_visual = "#aaaec2",
  border = "#989ca0",
  nontext = "#a1a5a9",
  linenr = "#6e7275",
  muted = "#666a6e",
  comment = "#52565a",
  punct = "#606468",
  fg = "#333639",
  fg_bright = "#16181a",

  red = "#ba3535",
  amber = "#bb5d00",
  yellow = "#886100",
  green = "#1d7d3e",
  teal = "#007475",
  blue = "#116bb5",
  magenta = "#993f94",

  kw = "#606468",
  fn = "#5143bb",
  remark = "#085f96",
  str = "#0d7974",
  const = "#9f4063",

  added = "#1d7d3e",
  removed = "#af470a",
  diff_add = "#bbc9bd",
  diff_delete = "#cfc1bb",
  diff_change = "#bbc9bd",
  diff_text = "#a6bfaa",
  search = "#dbaa6b",

  term = {
    "#26292c", "#ba3535", "#1d7d3e", "#886100", "#116bb5", "#993f94", "#007475", "#4e5154",
    "#4c4f52", "#d74745", "#2a904b", "#b08505", "#2b7ec9", "#ad51a7", "#008c8d", "#26292c",
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
  Comment = { fg = c.remark },
  Constant = { fg = c.const },
  String = { fg = c.str },
  Character = { fg = c.str },
  Number = { fg = c.const },
  Boolean = { fg = c.const },
  Float = { fg = c.const },
  Identifier = { fg = c.fg },
  Function = { fg = c.fn },
  Statement = { fg = c.kw },
  Conditional = { fg = c.kw },
  Repeat = { fg = c.kw },
  Label = { fg = c.kw },
  Operator = { fg = c.punct },
  Keyword = { fg = c.kw },
  Exception = { fg = c.kw },
  PreProc = { fg = c.kw },
  Include = { fg = c.kw },
  Define = { fg = c.kw },
  Macro = { fg = c.fn },
  PreCondit = { fg = c.kw },
  Type = { fg = c.fg },
  StorageClass = { fg = c.kw },
  Structure = { fg = c.fg },
  Typedef = { fg = c.fg },
  Special = { fg = c.const },
  SpecialChar = { fg = c.const },
  Tag = { fg = c.kw },
  Delimiter = { fg = c.punct },
  SpecialComment = { fg = c.remark },
  Debug = { fg = c.red },
  Underlined = { underline = true },
  Error = { fg = c.red },
  Todo = { fg = c.bg, bg = c.const, bold = true },

  -- treesitter
  -- Variables are plain at use; periwinkle marks their top-level definition.
  ["@variable"] = { fg = c.fg },
  ["@variable.builtin"] = { fg = c.fg },
  ["@variable.parameter"] = { fg = c.fg },
  -- Shell arguments, flags and $VAR uses are uses: plain.
  ["@variable.parameter.bash"] = { fg = c.fg },
  ["@constant.bash"] = { fg = c.fg },
  -- Members are plain, at use and at definition (keys, fields, attributes).
  ["@variable.member"] = { fg = c.fg },
  ["@property"] = { fg = c.fg },
  ["@variable.member.key"] = { fg = c.fg },
  ["@variable.member.attr"] = { fg = c.fg },
  -- Named constants are plain at use; literals stay c.const.
  ["@constant"] = { fg = c.fg },
  ["@constant.builtin"] = { fg = c.const },
  ["@constant.macro"] = { fg = c.fg },
  ["@module"] = { fg = c.fg },
  ["@module.builtin"] = { fg = c.fg },
  ["@label"] = { fg = c.kw },
  ["@string"] = { fg = c.str },
  ["@string.documentation"] = { fg = c.remark },
  ["@string.escape"] = { fg = c.const },
  ["@string.regexp"] = { fg = c.const },
  ["@string.special"] = { fg = c.const },
  ["@string.plain"] = { fg = c.str },
  ["@string.special.url"] = { fg = c.fn, underline = true },
  ["@character"] = { fg = c.str },
  ["@character.special"] = { fg = c.const },
  -- Names at their definition (after/queries); colour comes from the other captures.
  ["@declaration"] = {},
  ["@declaration.function"] = { fg = c.fn },
  ["@declaration.class"] = { fg = c.fn },
  ["@declaration.type"] = { fg = c.fn },
  ["@declaration.variable"] = { fg = c.fn },
  ["@number"] = { fg = c.const },
  ["@boolean"] = { fg = c.const },
  -- Types are plain; periwinkle marks them at their definition.
  ["@type"] = { fg = c.fg },
  ["@type.builtin"] = { fg = c.fg },
  ["@type.definition"] = { fg = c.fg },
  ["@attribute"] = { fg = c.const },
  ["@function"] = { fg = c.fn },
  -- Calls are plain; purple marks functions at their definition.
  ["@function.builtin"] = { fg = c.fg },
  ["@function.call"] = { fg = c.fg },
  ["@function.macro"] = { fg = c.fn },
  ["@function.method"] = { fg = c.fn },
  ["@function.method.call"] = { fg = c.fg },
  ["@constructor"] = { fg = c.fg },
  -- Python has no pure types; tree-sitter captures capitalised names as @type.
  ["@type.python"] = { fg = c.fg },
  ["@type.definition.python"] = { fg = c.fn },
  -- Lua captures table braces as @constructor.
  ["@constructor.lua"] = { link = "@punctuation.bracket" },
  ["@operator"] = { fg = c.punct },
  ["@keyword"] = { fg = c.kw },
  ["@keyword.function"] = { fg = c.kw },
  ["@keyword.operator"] = { fg = c.kw },
  ["@keyword.import"] = { fg = c.kw },
  ["@keyword.return"] = { fg = c.kw },
  ["@keyword.exception"] = { fg = c.kw },
  ["@keyword.conditional"] = { fg = c.kw },
  ["@keyword.repeat"] = { fg = c.kw },
  ["@keyword.coroutine"] = { fg = c.kw },
  ["@keyword.directive"] = { fg = c.kw },
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
  ["@markup.heading"] = { fg = c.fn, bold = true },
  ["@markup.quote"] = { fg = c.comment, italic = true },
  ["@markup.math"] = { fg = c.const },
  ["@markup.link"] = { fg = c.fn },
  ["@markup.link.label"] = { fg = c.fn },
  ["@markup.link.url"] = { fg = c.fn, underline = true },
  ["@markup.raw"] = { fg = c.str },
  ["@markup.list"] = { fg = c.punct },
  ["@markup.list.checked"] = { fg = c.green },
  ["@markup.list.unchecked"] = { fg = c.muted },
  ["@diff.plus"] = { fg = c.added },
  ["@diff.minus"] = { fg = c.removed },
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
  -- Cleared: tree-sitter marks parameters only at their definition.
  ["@lsp.type.parameter"] = {},
  ["@lsp.type.property"] = { link = "@property" },
  ["@lsp.type.struct"] = { link = "@type.definition" },
  ["@lsp.type.type"] = { link = "@type" },
  ["@lsp.type.typeParameter"] = { link = "@type.definition" },
  ["@lsp.type.variable"] = { link = "@variable" },
  ["@lsp.typemod.variable.declaration"] = {},
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
  Removed = { fg = c.removed },
  diffAdded = { fg = c.added },
  diffRemoved = { fg = c.removed },
  diffChanged = { fg = c.yellow },
  diffFile = { fg = c.fn },
  diffLine = { fg = c.muted },
  GitSignsAdd = { fg = c.added },
  GitSignsChange = { fg = c.yellow },
  GitSignsDelete = { fg = c.removed },
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
-- A class attribute at its definition takes the key colour.
-- A keyword-argument name is a use: plain, not the parameter teal.
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
        vim.lsp.semantic_tokens.highlight_token(t, ev.buf, ev.data.client_id, "@variable")
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
      vim.lsp.semantic_tokens.highlight_token(t, ev.buf, ev.data.client_id, "@variable.member.key")
    elseif object_key_def(ev.buf, t.line, t.start_col) then
      vim.lsp.semantic_tokens.highlight_token(t, ev.buf, ev.data.client_id, "@variable.member.key")
    end
  end,
})
