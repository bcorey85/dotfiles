-- dredge — personal theme-mode family, dark and light. Prose first, diffs second:
-- cool charcoal ground (OKLCH h 250), fg and greys tinted to the ground hue (C 0.025),
-- fg ~10.9:1. Contrast is tuned in APCA Lc, not WCAG ratios, which overrate
-- light-on-dark: each dark token's Lc is its light counterpart's x 0.88 (the fg
-- ratio), so both modes share one ladder. Syntax ranks by Lc, hue names the role, and
-- the more often a token appears the lower it ranks: functions (teal h 208) Lc 64,
-- strings (green h 152; below h 145 it turns pea green) 63, types (purple h 290)
-- 62, constants (pink h 350, C 0.09; builtins, booleans and self fold in) 60,
-- keywords (blue h 250, C 0.08, midway between teal and purple) 60, comments 56,
-- punctuation 51. Members and modules stay fg. Yellow and orange stay out of syntax.
-- Diffs: added = indigo signs on an indigo wash, removed = red, same washes as
-- hunk. Changed words separate by chroma, not lightness: fg holds >= 9:1.
-- Teal is the accent; yellow marks changed. The palette below is the source of truth; the
-- ghostty/herdr/hunk/starship/quickshell/claude-theme copies mirror it by hand.
-- Editing: one value at a time, judged on a real file in nvim and hunk before the
-- mirrors are touched. The Lc/dE numbers rule candidates out; they never pick one.
-- Body text never rises above fg; fg_bright is emphasis only.

local palettes = {}

palettes.dark = {
  bg = "#1c2023",
  bg_dark = "#171a1d",
  bg_line = "#24272a",
  bg_sel = "#2c3239",
  bg_visual = "#33393e",
  border = "#3a3e44",
  nontext = "#3d4348",
  linenr = "#747c83",
  muted = "#95a0ab",
  comment = "#a2afbd",
  punct = "#99a6b3",
  fg = "#c9d4e0",
  fg_bright = "#dfe7f0",

  red = "#f77972",
  amber = "#ffa475",
  yellow = "#ebc75b",
  green = "#82d395",
  teal = "#79cfcf",
  blue = "#7abff9",
  magenta = "#e091d8",

  kw = "#8db9e6",
  fn = "#66cad8",
  str = "#84c997",
  const = "#e5a1c0",
  type = "#b8aff5",

  added = "#69c7de",
  diff_add = "#1e232c",
  diff_delete = "#271f1f",
  diff_change = "#1e232c",
  diff_text = "#212f48",
  search = "#524028",

  term = {
    "#171a1d", "#f77972", "#82d395", "#ebc75b", "#7abff9", "#e091d8", "#79cfcf", "#c9d4e0",
    "#727c86", "#ff9790", "#a6e7b3", "#fdde8c", "#a0d4ff", "#efade8", "#a7e1e0", "#dfe7f0",
  },
}

-- Light: warm off-white (OKLCH L 0.955), greys tinted warm (h 70), fg ~10.3:1. Same
-- hues and ranks as dark: functions L 0.49 (5.3:1), string L 0.48 (5.4:1, >= 4.5:1 on
-- every diff wash), constants and types L 0.52-0.53 near max in-gamut chroma
-- (4.7-5.1:1), then comment L 0.56
-- (4.1:1) and keyword L 0.57 (4.1:1, C 0.10), punctuation L 0.60 (3.5:1).
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
  comment = "#7d7267",
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

  kw = "#3e6c9b",
  fn = "#006d79",
  str = "#1f6f3d",
  const = "#965877",
  type = "#675c9c",

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
  Type = { fg = c.type },
  StorageClass = { fg = c.kw },
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
  ["@variable.parameter"] = { fg = c.fg },
  ["@variable.member"] = { fg = c.fg },
  ["@property"] = { fg = c.fg },
  ["@constant"] = { fg = c.const },
  ["@constant.builtin"] = { fg = c.const },
  ["@constant.macro"] = { fg = c.const },
  ["@module"] = { fg = c.fg },
  ["@module.builtin"] = { fg = c.fg },
  ["@label"] = { fg = c.kw },
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
  ["@type.builtin"] = { fg = c.type },
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
