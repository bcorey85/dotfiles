vim.diagnostic.config({
  severity_sort = true,
  underline = true,
  virtual_text = { spacing = 2, source = "if_many", prefix = "●" },
  signs = {
    text = {
      [vim.diagnostic.severity.ERROR] = " ",
      [vim.diagnostic.severity.WARN] = " ",
      [vim.diagnostic.severity.HINT] = " ",
      [vim.diagnostic.severity.INFO] = " ",
    },
  },
})

vim.api.nvim_create_autocmd("LspAttach", {
  callback = function(args)
    local bufnr = args.buf
    local map = function(mode, lhs, rhs, desc)
      vim.keymap.set(mode, lhs, rhs, { buffer = bufnr, desc = desc })
    end

    map("n", "K", vim.lsp.buf.hover, "LSP Hover")
    map("n", "gd", function() Snacks.picker.lsp_definitions() end, "Go to definition")
    map("n", "gD", function() Snacks.picker.lsp_declarations() end, "Go to declaration")
    map("n", "gI", function() Snacks.picker.lsp_implementations() end, "Go to implementation")
    map("n", "gy", function() Snacks.picker.lsp_type_definitions() end, "Go to type definition")
    map("n", "gr", function() Snacks.picker.lsp_references() end, "References")
    map("n", "<leader>cr", vim.lsp.buf.rename, "Rename symbol")
    map({ "n", "v" }, "<leader>ca", vim.lsp.buf.code_action, "Code action")
    map("n", "<leader>cF", function() vim.lsp.buf.format({ async = true }) end, "Format buffer (LSP)")
    map("n", "gK", vim.lsp.buf.signature_help, "Signature help")

    map("n", "]d", function() vim.diagnostic.jump({ count = 1 }) end, "Next diagnostic")
    map("n", "[d", function() vim.diagnostic.jump({ count = -1 }) end, "Prev diagnostic")
    map("n", "]e", function() vim.diagnostic.jump({ count = 1, severity = vim.diagnostic.severity.ERROR }) end, "Next error")
    map("n", "[e", function() vim.diagnostic.jump({ count = -1, severity = vim.diagnostic.severity.ERROR }) end, "Prev error")
    map("n", "]w", function() vim.diagnostic.jump({ count = 1, severity = vim.diagnostic.severity.WARN }) end, "Next warning")
    map("n", "[w", function() vim.diagnostic.jump({ count = -1, severity = vim.diagnostic.severity.WARN }) end, "Prev warning")

    map("n", "<leader>cd", vim.diagnostic.open_float, "Line diagnostics")
    map("n", "<leader>cs", function() Snacks.picker.lsp_symbols() end, "Document symbols")
  end,
})

-- vtsls + vue_ls hybrid mode (Vue 3 / vue-language-server v3).
-- vtsls runs the TS server with @vue/typescript-plugin loaded, which gives it
-- awareness of .vue files. vue_ls handles Vue-specific work (template syntax,
-- SFC structure). The two servers talk via the plugin layer; vtsls owns TS,
-- vue_ls owns Vue.
local vue_language_server_path = vim.fn.stdpath("data")
  .. "/mason/packages/vue-language-server/node_modules/@vue/language-server"

local vue_plugin = {
  name = "@vue/typescript-plugin",
  location = vue_language_server_path,
  languages = { "vue" },
  configNamespace = "typescript",
}

vim.lsp.config("vtsls", {
  settings = {
    vtsls = {
      tsserver = {
        globalPlugins = { vue_plugin },
      },
    },
  },
  filetypes = { "typescript", "javascript", "javascriptreact", "typescriptreact", "vue" },
})

vim.lsp.config("vue_ls", {
  filetypes = { "vue" },
})

vim.lsp.config("eslint", {
  filetypes = {
    "javascript", "javascriptreact", "javascript.jsx",
    "typescript", "typescriptreact", "typescript.tsx",
    "vue",
  },
  settings = {
    workingDirectories = { mode = "auto" },
  },
})

vim.lsp.config("lua_ls", {
  settings = {
    Lua = {
      diagnostics = { globals = { "vim", "Snacks" } },
      workspace = { checkThirdParty = false },
      telemetry = { enable = false },
    },
  },
})

vim.lsp.config("pyright", {
  settings = {
    pyright = {
      disableOrganizeImports = true,
    },
    python = {
      analysis = {
        ignore = { "*" },
      },
    },
  },
})

vim.lsp.config("ruff", {
  on_attach = function(client)
    client.server_capabilities.hoverProvider = false
  end,
})

vim.lsp.config("cssls", {})
vim.lsp.config("html", {})
vim.lsp.config("jsonls", {
  settings = {
    json = {
      schemas = require("schemastore").json.schemas(),
      validate = { enable = true },
    },
  },
})
vim.lsp.config("yamlls", {
  settings = {
    yaml = {
      keyOrdering = false,
      schemaStore = {
        -- Disable yamlls's built-in schema fetcher so SchemaStore.nvim is the
        -- single source of truth; the plugin's `ignore`/override APIs only
        -- work if yamlls isn't also racing to load schemas.
        enable = false,
        url = "",
      },
      schemas = require("schemastore").yaml.schemas(),
    },
  },
})
vim.lsp.config("bashls", {})
vim.lsp.config("ansiblels", {})

-- oxlint has LSP mode (--lsp) and is in Mason registry as "oxlint"
-- It supports JS/TS/Vue filetypes via lspconfig definition
vim.lsp.config("oxlint", {})

vim.lsp.enable({
  "vtsls",
  "vue_ls",
  "eslint",
  "lua_ls",
  "pyright",
  "ruff",
  "cssls",
  "html",
  "jsonls",
  "yamlls",
  "bashls",
  "ansiblels",
  "oxlint",
})
