-- dredge — personal theme-mode family, dark and light. Prose first, diffs second:
-- cool charcoal ground (OKLCH L 0.265, h 250), fg and greys tinted to the ground hue
-- (C 0.025). Contrast is tuned in APCA Lc, not WCAG ratios, which overrate
-- light-on-dark. Dark is deliberately dim against halation: fg Lc 70 (~9.2:1),
-- comments 47, punctuation 46. Light: fg Lc 88. At Lc 75 on cream the gamut leaves
-- no chroma, and every token reads as black. Lc is a floor, not a target: coloured
-- token pairs also keep OKLab dE >= 0.09 in light, >= 0.085 in dark.
-- Loudness follows what the reader traces (go-to-definition, * search), not syntax.
-- Loud, at fg lightness: variables (fg), functions (teal h 197-202), parameters
-- and named constants (pink h 5). Middle: types (purple h 302-305), then literals
-- and builtins (green h 148-150, C 0.09-0.095, half a step above strings; None,
-- numbers, booleans, self; below h 145 it turns pea green). Quiet: strings (fg's
-- own blue h 246-250, C 0.09-0.10), keywords and builtin types
-- (grey italic, half a step above comments; italic carries the split, the
-- colours sit near dE 0.03-0.04). Members and modules stay fg.
-- Diffs: added = indigo signs on an indigo wash, removed = red, same washes as
-- hunk. Changed words separate by chroma, not lightness. Red reads louder than indigo,
-- so the removed wash carries less chroma and its word a touch more lift.
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
  comment = "#929fac",
  punct = "#929eab",
  fg = "#bdc8d3",
  fg_bright = "#d3dbe3",

  red = "#f77972",
  amber = "#ffa475",
  yellow = "#ebc75b",
  green = "#82d395",
  teal = "#79cfcf",
  blue = "#7abff9",
  magenta = "#e091d8",

  kw = "#9ca9b6",
  fn = "#63d3dc",
  str = "#7cb3e3",
  const = "#8ec695",
  type = "#c7aaea",
  param = "#e898aa",

  added = "#69c7de",
  diff_add = "#222730",
  diff_delete = "#2a2323",
  diff_change = "#222730",
  diff_text = "#25334c",
  search = "#56442c",

  term = {
    "#1a1d21", "#f77972", "#82d395", "#ebc75b", "#7abff9", "#e091d8", "#79cfcf", "#bdc8d3",
    "#727c86", "#ff9790", "#a6e7b3", "#fdde8c", "#a0d4ff", "#efade8", "#a7e1e0", "#d3dbe3",
  },
}

-- Light: warm off-white (OKLCH L 0.955), greys tinted warm (h 70), fg ~10.3:1.
-- Comment and punctuation L 0.60 (Lc 58).
palettes.light = {
  bg = "#f3efeb",
  bg_dark = "#efeae5",
  bg_line = "#ebe6e1",
  bg_sel = "#dcd7d1",
  bg_visual = "#d8dff7",
  border = "#c9c4bd",
  nontext = "#d3cdc5",
  linenr = "#b6ada5",
  muted = "#8f857b",
  comment = "#897e73",
  punct = "#897e74",
  fg = "#40362c",
  fg_bright = "#1e1a15",

  red = "#ba3535",
  amber = "#bb5d00",
  yellow = "#886100",
  green = "#1d7d3e",
  teal = "#007475",
  blue = "#116bb5",
  magenta = "#993f94",

  kw = "#7c7166",
  fn = "#1b595b",
  str = "#477cb1",
  const = "#397548",
  param = "#af556d",
  type = "#73539f",

  added = "#007a85",
  diff_add = "#e8edf7",
  diff_delete = "#f8e9e8",
  diff_change = "#e8edf7",
  diff_text = "#ccdfff",
  search = "#f4cd99",

  term = {
    "#40362c", "#ba3535", "#1d7d3e", "#886100", "#116bb5", "#993f94", "#007475", "#655c51",
    "#645a50", "#d74745", "#2a904b", "#b08505", "#2b7ec9", "#ad51a7", "#008c8d", "#40362c",
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
  Comment = { fg = c.comment },
  Constant = { fg = c.const },
  String = { fg = c.str },
  Character = { fg = c.str },
  Number = { fg = c.const },
  Boolean = { fg = c.const },
  Float = { fg = c.const },
  Identifier = { fg = c.fg },
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
  Type = { fg = c.type },
  StorageClass = { fg = c.kw, italic = true },
  Structure = { fg = c.type },
  Typedef = { fg = c.type },
  Special = { fg = c.const },
  SpecialChar = { fg = c.const },
  Tag = { fg = c.type },
  Delimiter = { fg = c.punct },
  SpecialComment = { fg = c.comment },
  Debug = { fg = c.red },
  Underlined = { underline = true },
  Error = { fg = c.red },
  Todo = { fg = c.bg, bg = c.const, bold = true },

  -- treesitter
  ["@variable"] = { fg = c.fg },
  ["@variable.builtin"] = { fg = c.const },
  ["@variable.parameter"] = { fg = c.param },
  ["@variable.member"] = { fg = c.fg },
  ["@property"] = { fg = c.fg },
  -- Named constants are traced like parameters; literals and builtins stay c.const.
  ["@constant"] = { fg = c.param },
  ["@constant.builtin"] = { fg = c.const },
  ["@constant.macro"] = { fg = c.param },
  ["@module"] = { fg = c.fg },
  ["@module.builtin"] = { fg = c.fg },
  ["@label"] = { fg = c.kw, italic = true },
  ["@string"] = { fg = c.str },
  ["@string.documentation"] = { fg = c.comment },
  ["@string.escape"] = { fg = c.const },
  ["@string.regexp"] = { fg = c.const },
  ["@string.special"] = { fg = c.const },
  ["@string.plain"] = { fg = c.const },
  ["@string.special.url"] = { fg = c.type, underline = true },
  ["@character"] = { fg = c.str },
  ["@character.special"] = { fg = c.const },
  ["@number"] = { fg = c.const },
  ["@boolean"] = { fg = c.const },
  ["@type"] = { fg = c.type },
  ["@type.builtin"] = { fg = c.kw, italic = true },
  ["@type.definition"] = { fg = c.type },
  ["@attribute"] = { fg = c.const },
  ["@function"] = { fg = c.fn },
  ["@function.builtin"] = { fg = c.fn },
  ["@function.call"] = { fg = c.fn },
  ["@function.macro"] = { fg = c.fn },
  ["@function.method"] = { fg = c.fn },
  ["@function.method.call"] = { fg = c.fn },
  ["@constructor"] = { fg = c.type },
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
  ["@punctuation.special"] = { fg = c.const },
  ["@comment"] = { link = "Comment" },
  ["@comment.error"] = { fg = c.red, bold = true },
  ["@comment.warning"] = { fg = c.yellow, bold = true },
  ["@comment.note"] = { fg = c.teal, bold = true },
  ["@comment.todo"] = { link = "Todo" },
  ["@tag"] = { fg = c.type },
  ["@tag.builtin"] = { fg = c.type },
  ["@tag.attribute"] = { fg = c.fn },
  ["@tag.delimiter"] = { fg = c.punct },
  ["@markup.strong"] = { bold = true },
  ["@markup.italic"] = { italic = true },
  ["@markup.strikethrough"] = { strikethrough = true },
  ["@markup.underline"] = { underline = true },
  ["@markup.heading"] = { fg = c.teal, bold = true },
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
  ["@lsp.type.class"] = { link = "@type" },
  ["@lsp.type.comment"] = {},
  ["@lsp.type.decorator"] = { link = "@attribute" },
  ["@lsp.type.enum"] = { link = "@type" },
  ["@lsp.type.enumMember"] = { link = "@constant" },
  -- Cleared: LSP marks function-valued variables and properties as functions.
  -- Tree-sitter colours only definitions and calls, the same as hunk.
  ["@lsp.type.function"] = {},
  ["@lsp.type.interface"] = { link = "@type" },
  ["@lsp.type.macro"] = { link = "@function.macro" },
  ["@lsp.type.method"] = {},
  ["@lsp.type.namespace"] = { link = "@module" },
  ["@lsp.type.parameter"] = { link = "@variable.parameter" },
  ["@lsp.type.property"] = { link = "@property" },
  ["@lsp.type.struct"] = { link = "@type" },
  ["@lsp.type.type"] = { link = "@type" },
  ["@lsp.type.typeParameter"] = { link = "@type" },
  ["@lsp.type.variable"] = { link = "@variable" },
  ["@lsp.typemod.variable.defaultLibrary"] = { link = "@variable.builtin" },
  ["@lsp.typemod.function.defaultLibrary"] = { link = "@function.builtin" },
  ["@lsp.typemod.class.defaultLibrary"] = { link = "@type.builtin" },
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
  -- added wash. Purple stays in the sign column and in side-by-side diffs.
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
