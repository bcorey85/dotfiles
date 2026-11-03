-- dredge-roles — dredge, with syntax coloured by what a token does, not what it is.
-- Binds violet: any name where it is introduced (function, class, variable, parameter, key).
-- Reads plain fg. Calls teal (decorators and constructors are calls). Writes orange:
-- a store into something that already exists. Exits magenta: return, raise, break, continue.
-- Literals yellow, types blue, comments olive, keywords and punctuation grey.
-- Everything outside syntax is dredge's own.

vim.cmd.runtime("colors/dredge.lua")
vim.g.colors_name = "dredge-roles"

local roles = {
  dark = {
    bind = "#8389dc", read = "#a0adb4", act = "#29a298", write = "#d66e31",
    exit = "#e34990", lit = "#bf983f", desc = "#1c90cb", remark = "#849900",
  },
  light = {
    bind = "#433fa8", read = "#202d37", act = "#00625c", write = "#943b12",
    exit = "#a80e62", lit = "#6d4a00", desc = "#005b91", remark = "#4f5d00",
  },
}
local role = roles[vim.o.background == "light" and "light" or "dark"]

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
  lit = {
    "String", "Character", "Number", "Boolean", "Float", "Constant", "Special", "SpecialChar",
    "@string", "@string.special", "@string.plain", "@string.escape", "@string.regexp",
    "@string.special.symbol", "@character", "@number", "@boolean", "@constant.builtin",
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
