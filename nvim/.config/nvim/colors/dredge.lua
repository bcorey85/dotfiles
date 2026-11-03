-- dredge — personal theme-mode family, dark and light: solarized-osaka's hues on
-- dredge's roles. Dark ground is slate (OKLCH L 0.205, h 225, C 0.030), midway
-- between charcoal and osaka's navy. Keywords, punctuation and line numbers are greys.
-- Functions and calls are violet (definitions not bold), strings teal, literals
-- magenta, types green, builtins and modules blue, parameters orange, attributes
-- and preprocessor red, comments yellow. Warnings take an amber, clear of the
-- orange parameters and the yellow comments. Markdown H1 is magenta, H2-H6 violet.
-- No italics: hunk can't render them, and the two must match.
-- Diffs take osaka's washes: teal add, deep-red remove. Signs (added, removed,
-- changed) fade toward the ground, 25% dark and 15% light, so the gutter sits under the text.
-- Teal is the accent; yellow marks changed. The palette below is the source of truth; the
-- ghostty/herdr/hunk/starship/quickshell/claude-theme copies mirror it by hand.
-- Editing: one value at a time, judged on a real file in nvim and hunk before the
-- mirrors are touched. The Lc/dE numbers rule candidates out; they never pick one.
-- Body text never rises above fg; fg_bright is emphasis only.

local palettes = {}

palettes.dark = {
  bg = "#061a21",
  bg_dark = "#01131a",
  bg_line = "#13272f",
  bg_cursor = "#0c2028",
  bg_sel = "#1e323a",
  bg_visual = "#243841",
  border = "#2a3e47",
  nontext = "#2e434b",
  linenr = "#777b82",
  muted = "#9b9fa6",
  comment = "#a8adb4",
  punct = "#7c8187",
  fg = "#a0adb4",
  fg_bright = "#d4dbe5",

  red = "#ed8c84",
  amber = "#f6a981",
  yellow = "#d7bb70",
  warn = "#e3a257",
  green = "#8dd09b",
  teal = "#29a298",
  blue = "#85beef",
  magenta = "#e34990",

  kw = "#858990",
  fn = "#7980d4",
  type = "#849900",
  builtin = "#1c90cb",
  param = "#d66e31",
  attr = "#de4f46",
  preproc = "#de4f46",
  remark = "#bf983f",
  str = "#29a298",
  const = "#e34990",

  added = "#29a298",
  removed = "#db302d",
  changed = "#b19950",
  diff_add = "#142d2e",
  diff_delete = "#2c0e0d",
  diff_change = "#142d2e",
  diff_text = "#173f3e",
  diff_text_delete = "#461312",
  search = "#5b4032",

  term = {
    "#01131a", "#ed8c84", "#8dd09b", "#d7bb70", "#85beef", "#e34990", "#29a298", "#c1c8d2",
    "#777b81", "#f9aea7", "#aee4b8", "#e9d296", "#a7d3f8", "#f37fae", "#9ad8d1", "#d4dbe5",
  },
}

-- Light: dim cream (OKLCH L 0.746, C 0.024, h 87). The ground ramp and washes
-- sit at 0.783 of a bright cream ramp; text keeps full-strength hues.
palettes.light = {
  bg = "#bbb4a4",
  bg_dark = "#b7b0a0",
  bg_line = "#b4ad9d",
  bg_cursor = "#b7b0a0",
  bg_sel = "#a9a292",
  bg_visual = "#a0a2b3",
  border = "#9a9384",
  nontext = "#a19a8b",
  linenr = "#60656b",
  muted = "#4e5158",
  comment = "#3e4148",
  punct = "#575b62",
  fg = "#202d37",
  fg_bright = "#131820",

  red = "#b0423f",
  amber = "#9e510f",
  yellow = "#846322",
  warn = "#7a4400",
  green = "#317a46",
  teal = "#00625c",
  blue = "#296caa",
  magenta = "#a80e62",

  kw = "#454950",
  fn = "#4b47b6",
  type = "#4f5d00",
  builtin = "#005b91",
  param = "#943b12",
  attr = "#a32822",
  preproc = "#a32822",
  remark = "#6d4a00",
  str = "#00625c",
  const = "#a80e62",

  added = "#038880",
  removed = "#d72d2b",
  changed = "#917031",
  diff_add = "#9bb1af",
  diff_delete = "#b7a8a5",
  diff_change = "#9bb1af",
  diff_text = "#72aca6",
  diff_text_delete = "#bb908b",
  search = "#a78773",

  -- Bright slots are deeper shades, as in solarized-osaka light: on a light
  -- ground a lighter "bright" colour reads fainter, not louder.
  term = {
    "#25292f", "#962929", "#0e5e2c", "#6b4b00", "#07538f", "#a0005c", "#005b55", "#4d5158",
    "#4b4f56", "#860914", "#004c15", "#5b3a00", "#00417d", "#82004b", "#004a44", "#25292f",
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
  Title = { fg = c.fn, bold = true },
  ErrorMsg = { fg = c.red },
  WarningMsg = { fg = c.warn },
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
  PreProc = { fg = c.preproc },
  Include = { fg = c.kw },
  Define = { fg = c.kw },
  Macro = { fg = c.fg },
  PreCondit = { fg = c.kw },
  Type = { fg = c.type },
  StorageClass = { fg = c.kw },
  Structure = { fg = c.type },
  Typedef = { fg = c.type },
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
  -- Variables are plain at use and at definition.
  ["@variable"] = { fg = c.fg },
  ["@variable.builtin"] = { fg = c.builtin },
  ["@variable.parameter"] = { fg = c.param },
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
  ["@module"] = { fg = c.builtin },
  ["@module.builtin"] = { fg = c.builtin },
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
  -- Violet marks functions only.
  ["@declaration.function"] = { fg = c.fn },
  ["@number"] = { fg = c.const },
  ["@boolean"] = { fg = c.const },
  ["@type"] = { fg = c.type },
  ["@type.builtin"] = { fg = c.type },
  ["@type.definition"] = { fg = c.type },
  ["@attribute"] = { fg = c.attr },
  ["@function"] = { fg = c.fn },
  ["@function.builtin"] = { fg = c.builtin },
  ["@function.call"] = { fg = c.fn },
  ["@function.macro"] = { fg = c.fg },
  ["@function.method"] = { fg = c.fn },
  ["@function.method.call"] = { fg = c.fn },
  ["@constructor"] = { fg = c.type },
  -- Python has no pure types; tree-sitter captures capitalised names as @type.
  ["@type.python"] = { fg = c.type },
  ["@type.definition.python"] = { fg = c.type == c.fg and c.fn or c.type },
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
  ["@comment.warning"] = { fg = c.warn, bold = true },
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
  ["@markup.quote"] = { fg = c.comment },
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
  -- Parameters take the orange at every use, so arguments show through the body.
  ["@lsp.type.parameter"] = { link = "@variable.parameter" },
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
  DiagnosticWarn = { fg = c.warn },
  DiagnosticInfo = { fg = c.blue },
  DiagnosticHint = { fg = c.teal },
  DiagnosticOk = { fg = c.green },
  DiagnosticUnderlineError = { sp = c.red, undercurl = true },
  DiagnosticUnderlineWarn = { sp = c.warn, undercurl = true },
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
