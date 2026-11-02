-- dredge — personal theme-mode family, dark and light. Prose first, diffs second:
-- charcoal ground (OKLCH L 0.232) with a whisper of blue (h 258, C 0.005). fg and fg_bright
-- carry more (C 0.016; light C 0.018) so they don't read warm. The text greys (keywords,
-- punctuation, line numbers, muted, quotes, ANSI greys) carry two thirds of it (C 0.011; light C 0.012).
-- Contrast is tuned in APCA Lc, not WCAG ratios, which overrate
-- light-on-dark. Dark is deliberately dim against halation: fg Lc 71,
-- definitions 47, comments 55, punctuation 33. Light: fg Lc 64, definitions 50, comments 48, punctuation 33. Lc is a floor, not a target: coloured
-- token pairs also keep OKLab dE >= 0.09 in light, >= 0.085 in dark.
-- Colour marks definitions; uses and calls are fg. Every definition is
-- indigo (h 285, leaning violet): top-level variables and constants, functions and
-- classes. Keys, fields, attributes, parameters and builtins (self, JSON) are
-- fg. Literals are dusty rose (h 5; light is pinker, h 355 C 0.14; None, numbers, booleans,
-- symbols, escapes, regex).
-- Strings are sea teal (h 182, dark L 0.72 C 0.070); comments are sand (h 80, C 0.020; light C 0.034). No italics: hunk can't render
-- them, and the two must match.
-- Light mirrors dark's hues and order: comments sit between fg and the
-- keywords. Code accents keep OKLab dE >= 0.17 from the near-black fg, or thin
-- strokes read as black; teal is chroma-capped in sRGB, so it gets there by lightness. Keywords are
-- the ground's grey, a step above punctuation, and so are markup tags. Types are fg.
-- Modules stay fg. Markdown headings are indigo, like definitions.
-- Diffs: added = green signs on a green wash (green is free: code never uses it),
-- removed = orange-red (h 38) on sign, rail and wash alike, clear of the rose
-- literals and the yellow change sign; same washes as hunk. Changed words
-- separate by chroma, not lightness. Red reads louder than green, so the
-- removed wash carries less chroma. Signs (added, removed, changed) fade toward
-- the ground, 25% dark and 15% light, so the gutter sits under the text.
-- Teal is the accent; yellow marks changed. The palette below is the source of truth; the
-- ghostty/herdr/hunk/starship/quickshell/claude-theme copies mirror it by hand.
-- Editing: one value at a time, judged on a real file in nvim and hunk before the
-- mirrors are touched. The Lc/dE numbers rule candidates out; they never pick one.
-- Body text never rises above fg; fg_bright is emphasis only.

local palettes = {}

palettes.dark = {
  bg = "#1c1e20",
  bg_dark = "#151719",
  bg_line = "#292b2d",
  bg_cursor = "#222426",
  bg_sel = "#343638",
  bg_visual = "#3b3c3e",
  border = "#414244",
  nontext = "#454648",
  linenr = "#777b82",
  muted = "#9b9fa6",
  comment = "#a8adb4",
  punct = "#7c8187",
  fg = "#c1c8d2",
  fg_bright = "#d4dbe5",

  red = "#ed8c84",
  amber = "#f6a981",
  yellow = "#d7bb70",
  green = "#8dd09b",
  teal = "#71b3a8",
  blue = "#85beef",
  magenta = "#c799c9",

  kw = "#858990",
  fn = "#9e9dd9",
  remark = "#b2a99d",
  str = "#71b3a8",
  const = "#cb8998",

  added = "#5da37e",
  removed = "#be6146",
  changed = "#b19950",
  diff_add = "#1e2a24",
  diff_delete = "#2d2423",
  diff_change = "#1e2a24",
  diff_text = "#154b2f",
  diff_text_delete = "#552b20",
  search = "#5b4032",

  term = {
    "#151719", "#ed8c84", "#8dd09b", "#d7bb70", "#85beef", "#c799c9", "#71b3a8", "#c1c8d2",
    "#777b81", "#f9aea7", "#aee4b8", "#e9d296", "#a7d3f8", "#d8b1d9", "#b1dfd6", "#d4dbe5",
  },
}

-- Light: light grey (OKLCH L 0.82) with the same whisper of blue (C 0.005). Accents sit around
-- L 0.47-0.52; luminance over contrast. Strings keep full chroma (C 0.087), or
-- they sit too close to the grey keywords.
palettes.light = {
  bg = "#c3c5c8",
  bg_dark = "#bec0c3",
  bg_line = "#babcbf",
  bg_cursor = "#bec0c3",
  bg_sel = "#adaeb0",
  bg_visual = "#abaebf",
  border = "#9a9c9f",
  nontext = "#a3a5a8",
  linenr = "#81868d",
  muted = "#666a71",
  comment = "#52565d",
  punct = "#7c8189",
  fg = "#30363f",
  fg_bright = "#131820",

  red = "#b0423f",
  amber = "#9e510f",
  yellow = "#846322",
  green = "#317a46",
  teal = "#18796d",
  blue = "#296caa",
  magenta = "#79437c",

  kw = "#6d7279",
  fn = "#574fa0",
  remark = "#6a5e4a",
  str = "#18796d",
  const = "#9d3a67",

  added = "#36885f",
  removed = "#b65a3e",
  changed = "#917031",
  diff_add = "#b4c5bc",
  diff_delete = "#cabdba",
  diff_change = "#b4c5bc",
  diff_text = "#99bfa7",
  diff_text_delete = "#caa59b",
  search = "#cba289",

  term = {
    "#25292f", "#b0423f", "#317a46", "#846322", "#296caa", "#79437c", "#18796d", "#4d5158",
    "#4b4f56", "#cc544f", "#3e8d53", "#ab8731", "#3d7ebe", "#8b538f", "#348b7f", "#25292f",
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
  -- Chrome is grey and fg; teal marks only what matches a query and the keys to press.
  FloatTitle = { fg = c.fg, bg = c.bg_dark, bold = true },
  FloatShadow = { bg = c.bg_dark, blend = 80 },
  FloatShadowThrough = { bg = c.bg_dark, blend = 100 },
  Cursor = { fg = c.bg, bg = c.fg_bright },
  -- The cursor band sits half bg_line's step off the ground; the number is fg, not an accent.
  CursorLine = { bg = c.bg_cursor },
  CursorColumn = { link = "CursorLine" },
  ColorColumn = { bg = c.bg_line },
  CursorLineNr = { fg = c.fg, bold = true },
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
  PmenuKind = { fg = c.muted, bg = c.bg_dark },
  PmenuExtra = { fg = c.muted, bg = c.bg_dark },
  PmenuSbar = { bg = c.bg_line },
  PmenuThumb = { bg = c.border },
  PmenuMatch = { fg = c.teal, bold = true },
  WildMenu = { link = "PmenuSel" },
  Visual = { bg = c.bg_visual },
  VisualNOS = { link = "Visual" },
  Search = { fg = c.fg_bright, bg = c.search },
  -- Matches and the current match are one amber family: a wash, then solid amber.
  IncSearch = { fg = c.bg, bg = c.amber, bold = true },
  CurSearch = { link = "IncSearch" },
  Substitute = { fg = c.bg, bg = c.magenta },
  MatchParen = { fg = c.teal, bg = c.bg_visual, bold = true },
  NonText = { fg = c.nontext },
  Whitespace = { fg = c.nontext },
  EndOfBuffer = { fg = c.bg },
  SpecialKey = { fg = c.nontext },
  Conceal = { fg = c.muted },
  Directory = { fg = c.fg, bold = true },
  Title = { fg = c.teal, bold = true },
  ErrorMsg = { fg = c.red },
  WarningMsg = { fg = c.yellow },
  MoreMsg = { fg = c.green },
  OkMsg = { fg = c.green },
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
  Macro = { fg = c.fg },
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
  -- Variables are plain at use; indigo marks their top-level definition.
  ["@variable"] = { fg = c.fg },
  ["@variable.builtin"] = { fg = c.fg },
  ["@variable.parameter"] = { fg = c.fg },
  -- Shell arguments, flags and $VAR uses are uses: plain.
  ["@variable.parameter.bash"] = { fg = c.fg },
  ["@constant.bash"] = { fg = c.fg },
  ["@string.special.path.bash"] = { fg = c.fg },
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
  -- The regex injection captures class characters, `.` and group names as code; they are literals.
  ["@constant.regex"] = { fg = c.const },
  ["@variable.builtin.regex"] = { fg = c.const },
  ["@property.regex"] = { fg = c.const },
  ["@string.special"] = { fg = c.str },
  ["@string.special.symbol"] = { fg = c.const },
  ["@string.plain"] = { fg = c.str },
  ["@string.special.url"] = { fg = c.fn, underline = true },
  ["@character"] = { fg = c.str },
  ["@character.special"] = { fg = c.punct },
  -- Names at their definition (after/queries); colour comes from the other captures.
  ["@declaration"] = {},
  ["@declaration.function"] = { fg = c.fn },
  ["@declaration.class"] = { fg = c.fn },
  ["@declaration.type"] = { fg = c.fn },
  ["@declaration.variable"] = { fg = c.fn },
  ["@number"] = { fg = c.const },
  ["@boolean"] = { fg = c.const },
  -- Types are plain; indigo marks them at their definition.
  ["@type"] = { fg = c.fg },
  ["@type.builtin"] = { fg = c.fg },
  ["@type.definition"] = { fg = c.fg },
  ["@attribute"] = { fg = c.fg },
  ["@function"] = { fg = c.fn },
  -- Calls are plain; purple marks functions at their definition.
  ["@function.builtin"] = { fg = c.fg },
  ["@function.call"] = { fg = c.fg },
  ["@function.macro"] = { fg = c.fg },
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
  ["@markup.math"] = { fg = c.str },
  ["@markup.link"] = { fg = c.fn },
  ["@markup.link.label"] = { fg = c.fn },
  ["@markup.link.url"] = { fg = c.fn, underline = true },
  ["@markup.raw"] = { fg = c.str },
  ["@markup.list"] = { fg = c.punct },
  ["@markup.list.checked"] = { fg = c.green },
  ["@markup.list.unchecked"] = { fg = c.muted },
  ["@diff.plus"] = { fg = c.added },
  ["@diff.minus"] = { fg = c.removed },
  ["@diff.delta"] = { fg = c.changed },

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
  Changed = { fg = c.changed },
  Removed = { fg = c.removed },
  diffAdded = { fg = c.added },
  diffRemoved = { fg = c.removed },
  diffChanged = { fg = c.changed },
  diffFile = { fg = c.fn },
  diffLine = { fg = c.muted },
  GitSignsAdd = { fg = c.added },
  GitSignsChange = { fg = c.changed },
  GitSignsDelete = { fg = c.removed },
  -- Staged hunks are done: grey, so only unstaged work carries colour.
  GitSignsStagedAdd = { fg = c.linenr },
  GitSignsStagedChange = { fg = c.linenr },
  GitSignsStagedChangedelete = { fg = c.linenr },
  GitSignsStagedDelete = { fg = c.linenr },
  GitSignsStagedTopdelete = { fg = c.linenr },
  GitSignsStagedUntracked = { fg = c.linenr },
  -- Inline overlay shows the old line in rose above, so changed lines take the
  -- added wash.
  GitSignsChangeLn = { link = "DiffAdd" },

  -- plugins
  -- flash dims the buffer while it waits for a label; grey, not the sand comment.
  FlashBackdrop = { fg = c.kw },
  -- No blocks: the typed letters turn bright; the jump label is amber, underlined to part it from them.
  FlashMatch = { fg = c.fg_bright },
  FlashCurrent = { link = "FlashMatch" },
  FlashLabel = { fg = c.amber, bold = true, underline = true },
  SnacksPickerDir = { fg = c.comment },
  SnacksPickerMatch = { fg = c.teal, bold = true },
  SnacksPickerPrompt = { fg = c.muted },
  -- fyler copies Directory's fg without bold, and ships One Dark git colours.
  FylerDirectoryName = { link = "Directory" },
  FylerDirectoryIcon = { link = "Directory" },
  -- Every change is green and the mark after the name says which; only a conflict is red.
  FylerGitModified = { fg = c.added },
  FylerGitRenamed = { fg = c.added },
  FylerGitStaged = { fg = c.added },
  FylerGitDeleted = { fg = c.added },
  FylerGitUntracked = { fg = c.added },
  FylerGitConflict = { fg = c.removed },
  -- Neogit derives its own greys from Normal, so every group it colours is set here.
  NeogitSectionHeader = { fg = c.fn, bold = true },
  NeogitUnmergedInto = { link = "NeogitSectionHeader" },
  NeogitUnpushedTo = { link = "NeogitSectionHeader" },
  NeogitUnpulledFrom = { link = "NeogitSectionHeader" },
  NeogitBranch = { fg = c.fn },
  NeogitBranchHead = { fg = c.fn, bold = true },
  NeogitRemote = { fg = c.blue },
  NeogitTagName = { fg = c.yellow },
  NeogitTagDistance = { fg = c.muted },
  NeogitFilePath = { fg = c.fg },
  NeogitCommitViewHeader = { fg = c.fg_bright, bg = c.bg_sel, bold = true },
  NeogitActiveItem = { bg = c.bg_sel },
  NeogitFloatHeaderHighlight = { fg = c.teal, bold = true },
  NeogitPopupSwitchKey = { fg = c.teal },
  NeogitPopupOptionKey = { fg = c.teal },
  NeogitPopupConfigKey = { fg = c.teal },
  NeogitPopupActionKey = { fg = c.teal },
  -- Fyler's rule: every change is green, only a conflict is red.
  NeogitChangeModified = { fg = c.added },
  NeogitChangeAdded = { fg = c.added },
  NeogitChangeNewFile = { fg = c.added },
  NeogitChangeDeleted = { fg = c.added },
  NeogitChangeRenamed = { fg = c.added },
  NeogitChangeCopied = { fg = c.added },
  NeogitChangeUpdated = { fg = c.added },
  NeogitChangeUnmerged = { fg = c.red, bold = true },
  NeogitHunkHeader = { fg = c.muted, bg = c.bg_line },
  NeogitHunkHeaderHighlight = { fg = c.fg, bg = c.bg_sel },
  NeogitHunkHeaderCursor = { link = "NeogitHunkHeaderHighlight" },
  NeogitHunkMergeHeader = { fg = c.red, bg = c.bg_line, bold = true },
  NeogitHunkMergeHeaderHighlight = { fg = c.red, bg = c.bg_sel, bold = true },
  NeogitHunkMergeHeaderCursor = { link = "NeogitHunkMergeHeaderHighlight" },
  NeogitDiffHeader = { fg = c.fn, bg = c.bg_sel, bold = true },
  NeogitDiffHeaderHighlight = { fg = c.fn, bg = c.bg_visual, bold = true },
  -- The hunk under the cursor gets a band; the cursor row a neutral one that keeps its sign colour.
  NeogitDiffContext = { bg = c.bg },
  NeogitDiffContextHighlight = { bg = c.bg_cursor },
  NeogitDiffContextCursor = { bg = c.bg_line },
  NeogitDiffAdd = { fg = c.added, bg = c.diff_add },
  NeogitDiffAddHighlight = { link = "NeogitDiffAdd" },
  NeogitDiffAddCursor = { fg = c.added, bg = c.bg_line },
  NeogitDiffDelete = { fg = c.removed, bg = c.diff_delete },
  NeogitDiffDeleteHighlight = { link = "NeogitDiffDelete" },
  NeogitDiffDeleteCursor = { fg = c.removed, bg = c.bg_line },
  NeogitDiffAdditions = { fg = c.added },
  NeogitDiffDeletions = { fg = c.removed },
  NeogitDiffAddInline = { bg = c.diff_text },
  NeogitDiffDeleteInline = { bg = c.diff_text_delete },
  NeogitGraphAuthor = { fg = c.amber },
  NeogitGraphRed = { fg = c.red },
  NeogitGraphWhite = { fg = c.fg },
  NeogitGraphYellow = { fg = c.yellow },
  NeogitGraphGreen = { fg = c.green },
  NeogitGraphCyan = { fg = c.teal },
  NeogitGraphBlue = { fg = c.blue },
  NeogitGraphPurple = { fg = c.magenta },
  NeogitGraphGray = { fg = c.muted },
  NeogitGraphOrange = { fg = c.amber },
  NeogitGraphBoldRed = { fg = c.red, bold = true },
  NeogitGraphBoldWhite = { fg = c.fg, bold = true },
  NeogitGraphBoldYellow = { fg = c.yellow, bold = true },
  NeogitGraphBoldGreen = { fg = c.green, bold = true },
  NeogitGraphBoldCyan = { fg = c.teal, bold = true },
  NeogitGraphBoldBlue = { fg = c.blue, bold = true },
  NeogitGraphBoldPurple = { fg = c.magenta, bold = true },
  NeogitGraphBoldGray = { fg = c.muted, bold = true },
  NeogitGraphBoldOrange = { fg = c.amber, bold = true },
  -- barbar's jump letters ship pure red; amber bold, like flash labels.
  BufferCurrentTarget = { fg = c.amber, bg = c.bg, bold = true },
  BufferVisibleTarget = { fg = c.amber, bg = c.bg_dark, bold = true },
  BufferInactiveTarget = { fg = c.amber, bg = c.bg_dark, bold = true },
  BufferAlternateTarget = { fg = c.amber, bg = c.bg_dark, bold = true },
  -- codediff colours the numbers on changed rows with the row's own wash.
  CodeDiffGutterInsertNumber = { fg = c.added },
  CodeDiffGutterDeleteNumber = { fg = c.removed },
  CodeDiffMoveFrom = { fg = c.blue },
  CodeDiffMoveTo = { fg = c.blue },
  CodeDiffFiller = { fg = c.nontext },
  MiniClueDescGroup = { fg = c.muted },
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
