vim.diagnostic.config({
  severity_sort = true,
  underline = true,
  -- Inline diagnostics are rendered by tiny-inline-diagnostic.nvim (cursor-line
  -- focused), so the native virtual_text is disabled to avoid double display.
  virtual_text = false,
  signs = {
    text = {
      [vim.diagnostic.severity.ERROR] = " ",
      [vim.diagnostic.severity.WARN] = " ",
      [vim.diagnostic.severity.HINT] = " ",
      [vim.diagnostic.severity.INFO] = " ",
    },
  },
})

-- Diagnostic navigation + float live at global scope, not in LspAttach: nvim-lint
-- produces diagnostics in buffers with no LSP client (markdown, shell, etc.), so
-- these must work everywhere — not only where a language server attached.
local dmap = function(lhs, rhs, desc)
  vim.keymap.set("n", lhs, rhs, { desc = desc })
end

dmap("]d", function()
  vim.diagnostic.jump({ count = 1 })
end, "Next diagnostic")
dmap("[d", function()
  vim.diagnostic.jump({ count = -1 })
end, "Prev diagnostic")
dmap("]e", function()
  vim.diagnostic.jump({ count = 1, severity = vim.diagnostic.severity.ERROR })
end, "Next error")
dmap("[e", function()
  vim.diagnostic.jump({ count = -1, severity = vim.diagnostic.severity.ERROR })
end, "Prev error")
dmap("]w", function()
  vim.diagnostic.jump({ count = 1, severity = vim.diagnostic.severity.WARN })
end, "Next warning")
dmap("[w", function()
  vim.diagnostic.jump({ count = -1, severity = vim.diagnostic.severity.WARN })
end, "Prev warning")

-- Line diagnostics float lives in the <leader>l (lsp/diag/qf) group alongside the
-- diagnostic→quickfix/loclist lists, not in <leader>c (code mutation). Document
-- symbols moved out entirely — <leader>ss (snacks search) already covers it.
dmap("<leader>ll", vim.diagnostic.open_float, "Line diagnostics (float)")

-- Remove Neovim's built-in gr* LSP default keymaps (gra/gri/grn/grr/grt/grx,
-- created globally at startup in core's _defaults.lua). They're redundant here —
-- the LspAttach maps below cover the same actions and route through Snacks
-- pickers for previews. Deleting them also stops bare `gr` (our References map)
-- from stalling for timeoutlen waiting on a `gr*` continuation, and clears the
-- mini.clue popup that listed them by their raw `vim.lsp.buf.*()` descriptions.
-- pcall per key: silently skips any the running Neovim version doesn't define.
for _, k in ipairs({ "gra", "gri", "grn", "grr", "grt", "grx" }) do
  pcall(vim.keymap.del, "n", k)
end

vim.api.nvim_create_autocmd("LspAttach", {
  callback = function(args)
    local bufnr = args.buf
    local map = function(mode, lhs, rhs, desc)
      vim.keymap.set(mode, lhs, rhs, { buffer = bufnr, desc = desc })
    end

    map("n", "K", vim.lsp.buf.hover, "LSP Hover")
    map("n", "gd", vim.lsp.buf.definition, "Go to definition")
    map("n", "gD", vim.lsp.buf.declaration, "Go to declaration")
    map("n", "gI", function()
      Snacks.picker.lsp_implementations()
    end, "Go to implementation")
    map("n", "gy", vim.lsp.buf.type_definition, "Go to type definition")
    map("n", "gr", function()
      Snacks.picker.lsp_references()
    end, "References")
    map("n", "<leader>lr", vim.lsp.buf.rename, "Rename symbol")
    map({ "n", "v" }, "<leader>la", vim.lsp.buf.code_action, "Code action")
    map("n", "<leader>lF", function()
      vim.lsp.buf.format({ async = true })
    end, "Format buffer (LSP)")
    map("n", "gK", vim.lsp.buf.signature_help, "Signature help")

    local client = vim.lsp.get_client_by_id(args.data.client_id)
    if client and client:supports_method("textDocument/documentHighlight") then
      local hl_group = vim.api.nvim_create_augroup("lsp_document_highlight_" .. bufnr, { clear = true })
      vim.api.nvim_create_autocmd({ "CursorHold", "CursorHoldI" }, {
        group = hl_group,
        buffer = bufnr,
        callback = vim.lsp.buf.document_highlight,
      })
      vim.api.nvim_create_autocmd({ "CursorMoved", "CursorMovedI" }, {
        group = hl_group,
        buffer = bufnr,
        callback = vim.lsp.buf.clear_references,
      })
    end
  end,
})

-- Clean up per-buffer document-highlight augroups on detach. Augroups created
-- in LspAttach are named per-buffer but are never auto-deleted — they leak for
-- the session lifetime. Only tear down when the LAST client that supports
-- textDocument/documentHighlight leaves the buffer; if another highlight-capable
-- client is still attached, the group (and its autocmds) must remain.
vim.api.nvim_create_autocmd("LspDetach", {
  callback = function(args)
    local bufnr = args.buf
    local detaching_id = args.data.client_id

    local remaining = vim.tbl_filter(function(c)
      return c.id ~= detaching_id and c:supports_method("textDocument/documentHighlight")
    end, vim.lsp.get_clients({ bufnr = bufnr }))

    if #remaining == 0 then
      pcall(vim.api.nvim_del_augroup_by_name, "lsp_document_highlight_" .. bufnr)
      -- buf_clear_references targets bufnr explicitly; LspDetach can fire for a
      -- background buffer, where clear_references() would hit the wrong one.
      vim.lsp.util.buf_clear_references(bufnr)
    end
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

-- lspconfig's eslint root_dir only checks for a config file, so a project
-- with an eslint config but uninstalled deps spawns a server that instantly
-- fails with "[lspconfig] Unable to find ESLint library". Wrap the base
-- root_dir with a library check (node_modules walk from the buffer up to the
-- project root, Yarn PnP, or a global install) and skip startup otherwise.
local base_eslint_root_dir = vim.lsp.config.eslint.root_dir

local function eslint_lib_available(bufname, root)
  for dir in vim.fs.parents(bufname) do
    if vim.uv.fs_stat(dir .. "/node_modules/eslint") then
      return true
    end
    if dir == root then
      break
    end
  end
  return vim.uv.fs_stat(root .. "/.pnp.cjs") ~= nil
    or vim.uv.fs_stat(root .. "/.pnp.js") ~= nil
    or vim.fn.executable("eslint") == 1
end

vim.lsp.config("eslint", {
  filetypes = {
    "javascript",
    "javascriptreact",
    "javascript.jsx",
    "typescript",
    "typescriptreact",
    "typescript.tsx",
    "vue",
  },
  settings = {
    workingDirectories = { mode = "auto" },
  },
  root_dir = function(bufnr, on_dir)
    base_eslint_root_dir(bufnr, function(root)
      if eslint_lib_available(vim.api.nvim_buf_get_name(bufnr), root) then
        on_dir(root)
      end
    end)
  end,
})

vim.lsp.config("lua_ls", {
  settings = {
    Lua = {
      diagnostics = { globals = { "vim" } },
      workspace = { checkThirdParty = false },
      telemetry = { enable = false },
    },
  },
})

-- pyright + ruff division of labour: ruff owns all lint diagnostics (faster,
-- project-aware), so pyright's analysis diagnostics are silenced via
-- python.analysis.ignore = { "*" } to avoid duplicate/conflicting reports.
-- pyright is kept alive for hover, completion, go-to-definition, and rename —
-- the things ruff doesn't provide. Pairing with ruff's hoverProvider = false
-- (below) ensures K always resolves through pyright, not ruff's bare-bones hover.
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

vim.lsp.config("jsonls", {
  settings = {
    json = {
      validate = { enable = true },
    },
  },
})
vim.lsp.config("yamlls", {
  settings = {
    yaml = {
      keyOrdering = false,
      -- Use yamlls's built-in SchemaStore catalog fetcher (default url).
      schemaStore = {
        enable = true,
      },
    },
  },
})

-- cssls, html, bashls, taplo, ansiblels, and oxlint need no extra config —
-- vim.lsp.enable(config.servers) below activates them with lspconfig's
-- shipped defaults (servers.lua is the source of truth for the list).
vim.lsp.enable(require("config.servers"))
