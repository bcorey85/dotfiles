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
    map("n", "gd", vim.lsp.buf.definition, "Go to definition")
    map("n", "gD", vim.lsp.buf.declaration, "Go to declaration")
    map("n", "gI", vim.lsp.buf.implementation, "Go to implementation")
    map("n", "gy", vim.lsp.buf.type_definition, "Go to type definition")
    map("n", "gr", vim.lsp.buf.references, "References")
    map("n", "<leader>cr", vim.lsp.buf.rename, "Rename symbol")
    map({ "n", "v" }, "<leader>ca", vim.lsp.buf.code_action, "Code action")
    map("n", "<leader>cf", function() vim.lsp.buf.format({ async = true }) end, "Format buffer")
    map("n", "gK", vim.lsp.buf.signature_help, "Signature help")

    map("n", "]d", function() vim.diagnostic.jump({ count = 1 }) end, "Next diagnostic")
    map("n", "[d", function() vim.diagnostic.jump({ count = -1 }) end, "Prev diagnostic")
    map("n", "]e", function() vim.diagnostic.jump({ count = 1, severity = vim.diagnostic.severity.ERROR }) end, "Next error")
    map("n", "[e", function() vim.diagnostic.jump({ count = -1, severity = vim.diagnostic.severity.ERROR }) end, "Prev error")
    map("n", "]w", function() vim.diagnostic.jump({ count = 1, severity = vim.diagnostic.severity.WARN }) end, "Next warning")
    map("n", "[w", function() vim.diagnostic.jump({ count = -1, severity = vim.diagnostic.severity.WARN }) end, "Prev warning")

    map("n", "<leader>cd", vim.diagnostic.open_float, "Line diagnostics")
    map("n", "<leader>cs", vim.lsp.buf.document_symbol, "Document symbols")
  end,
})

local vue_ls_path = vim.fn.stdpath("data")
  .. "/mason/packages/vue-language-server/node_modules/@vue/language-server"

local vue_plugin = {
  name = "@vue/typescript-plugin",
  location = vue_ls_path,
  languages = { "vue" },
  configNamespace = "typescript",
}

local ts_filetypes = { "typescript", "javascript", "javascriptreact", "typescriptreact", "vue" }

vim.lsp.config("ts_ls", {
  init_options = {
    plugins = { vue_plugin },
  },
  filetypes = ts_filetypes,
})

vim.lsp.config("vue_ls", {
  filetypes = { "vue" },
  init_options = {
    typescript = {
      tsdk = vim.fn.stdpath("data") .. "/mason/packages/typescript-language-server/node_modules/typescript/lib",
    },
  },
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
vim.lsp.config("jsonls", {})
vim.lsp.config("yamlls", {
  settings = {
    yaml = {
      keyOrdering = false,
    },
  },
})
vim.lsp.config("bashls", {})
vim.lsp.config("ansiblels", {})

-- oxlint has LSP mode (--lsp) and is in Mason registry as "oxlint"
-- It supports JS/TS/Vue filetypes via lspconfig definition
vim.lsp.config("oxlint", {})

vim.lsp.enable({
  "ts_ls",
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
