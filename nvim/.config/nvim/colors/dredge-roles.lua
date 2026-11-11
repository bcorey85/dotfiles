-- dredge-roles — dredge, with syntax coloured by what a token does, not what it is.
-- Binds violet: any name where it is introduced (function, class, variable, parameter, key).
-- Reads plain fg. Calls teal (decorators and constructors are calls). Writes orange:
-- a store into something that already exists. Exits magenta: return, raise, break, continue.
-- Literals olive, strings included. Keywords grey, types blue. Comments yellow.
-- Everything outside syntax is dredge's own.

vim.cmd.runtime("colors/dredge.lua")
vim.g.colors_name = "dredge-roles"

local roles = {
  dark = {
    bind = "#9299ee", read = "#b6c3cb", act = "#46b8ae", write = "#ee8448",
    exit = "#f861a4", lit = "#99af2e", kw = "#9a9ea5", desc = "#3ba6e2", remark = "#c59f49",
  },
  -- Orange, green and blue sit at the hues where a dark shade keeps the most chroma.
  -- Teal and green sit lighter, at full chroma for their lightness.
  light = {
    bind = "#433fa8", read = "#293741", act = "#006c66", write = "#992406",
    exit = "#a80e62", lit = "#2a7000", kw = "#4c5158", desc = "#07549f", remark = "#6d4a00",
  },
}
local mode = vim.o.background == "light" and "light" or "dark"
-- A variant (colors/dredge-roles-warm.lua) swaps role colours through vim.g.dredge_role_overrides.
local role_overrides = vim.g.dredge_role_overrides or {}
local role = vim.tbl_extend("force", roles[mode], role_overrides[mode] or {})

local by_role = {
  bind = {
    "Function", "@function", "@function.method",
    "@declaration.function", "@declaration.class", "@declaration.type",
    "@declaration.variable", "@declaration.local",
    "@variable.parameter", "@variable.member.key", "@variable.member.attr",
    "@type.definition", "@type.definition.python",
    "@lsp.mod.declaration", "@lsp.mod.definition",
  },
  read = {
    "Identifier", "@variable", "@variable.builtin", "@variable.kwarg",
    "@variable.parameter.bash", "@module", "@module.builtin", "@constant", "@constant.macro",
    "@type.sql",
  },
  act = {
    "Macro", "@function.call", "@function.method.call", "@function.builtin",
    "@function.macro", "@constructor", "@attribute", "PreProc",
  },
  write = { "@variable.write", "@lsp.mod.mutable" },
  exit = { "@keyword.return", "@keyword.exit" },
  kw = {
    "Statement", "Conditional", "Repeat", "Label", "Keyword", "Exception", "Include",
    "Define", "PreCondit", "StorageClass", "@label",
    "@keyword", "@keyword.function", "@keyword.operator", "@keyword.import",
    "@keyword.exception", "@keyword.conditional", "@keyword.repeat", "@keyword.coroutine",
    "@keyword.directive", "@keyword.modifier", "@keyword.type",
  },
  lit = {
    "String", "@string", "@string.special", "@string.plain", "@string.special.symbol",
    "Character", "Number", "Boolean", "Float", "Constant", "Special", "SpecialChar",
    "@string.escape", "@string.regexp", "@character", "@number", "@boolean", "@constant.builtin",
    "@constant.regex", "@variable.builtin.regex", "@property.regex",
  },
  remark = { "Comment", "SpecialComment", "@comment", "@string.documentation" },
  desc = {
    "Type", "Structure", "Typedef", "@type", "@type.builtin", "@type.python",
  },
}

for name, groups in pairs(by_role) do
  for _, group in ipairs(groups) do
    vim.api.nvim_set_hl(0, group, { fg = role[name] })
  end
end

-- LSP token types defer to tree-sitter, which knows a call from a reference;
-- the declaration modifier alone marks a bind.
local lsp_links = {
  ["@lsp.type.class"] = {},
  ["@lsp.type.parameter"] = { link = "@variable" },
  ["@lsp.type.interface"] = { link = "@type" },
  ["@lsp.type.struct"] = { link = "@type" },
  ["@lsp.type.typeParameter"] = { link = "@type" },
  ["@lsp.typemod.variable.readonly.python"] = { link = "@variable" },
}
for group, spec in pairs(lsp_links) do
  vim.api.nvim_set_hl(0, group, spec)
end
