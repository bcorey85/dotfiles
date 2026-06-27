-- vim.pack bootstrap — replaces lazy.nvim.
--
-- vim.pack has no lazy-loading: every plugin installs to
--   ~/.local/share/nvim/site/pack/core/opt/<name>
-- and is added to the runtimepath at startup. Each lua/plugins/<name>.lua
-- returns a spec (or a list of specs):
--
--   {
--     src      = "owner/repo" | full git URL,   -- github shorthand is expanded
--     name     = "dir-name",                     -- optional; defaults to repo name
--     version  = "branch"|"tag"| vim.version.range(...),  -- optional
--     build    = function(ev_data) ... end,      -- optional; runs on install/update
--     deps     = { spec, ... },                  -- optional; installed BEFORE src
--     cond     = function() return bool end,     -- optional; skip when false
--     setup    = function() ... end,             -- optional; runs after add(), in order
--   }
--
-- Flow: walk plugin_order, collect every source (deps before their dependent),
-- run a single vim.pack.add, fire build hooks via PackChanged, then call each
-- plugin's setup() in declared order. Order is explicit (not globbed) because it
-- matters: theme first (colorscheme), treesitter before its consumers, mason
-- before mason-lspconfig, etc.

-- Deterministic load order. Deps are pulled in per-spec, so only top-level
-- plugins are listed here.
--
-- All mini.* modules share a single "echasnovski/mini.nvim" monorepo src.
-- register() dedupes by derived repo name ("mini.nvim"), so the repo is
-- cloned once regardless of how many spec files declare it. Each file's
-- setup() still runs independently in the order listed here.
local plugin_order = {
  "theme", -- colorscheme — must be first
  "mini-icons", -- icon mock (satisfies require("nvim-web-devicons")) — before consumers
  "treesitter", -- before markview / mini.ai textobjects
  "treesitter-context", -- sticky scope header — after treesitter
  "matchup", -- `%` matches keyword/tag pairs (function/end, <div></div>) — after treesitter
  "lspconfig", -- ships lsp/ server defs consumed by config.lsp
  "mason", -- LSP / tool installer (3 plugins)
  "blink", -- completion
  "snacks", -- finder (snacks.picker, replaced mini.pick) + image/zen/scratch/terminal/gitbrowse; before obsidian (picker) + lsp consumers
  "oil",
  "smart-splits",
  "gitsigns",
  "neogit",
  "diffs", -- treesitter syntax highlighting for diff-mode diffs (display only)
  "diffview", -- 3-way merge tool + diff/history viewer (neogit delegates conflicts here)
  "octo", -- GitHub issues/PRs (forge port) — after snacks (picker) + mini-icons (devicons mock)
  "mini-ai",
  "mini-surround",
  "mini-pairs",
  "mini-indentscope",
  "mini-clue", -- key-clue hints (replaced which-key)
  "ts-comments",
  "vim-repeat", -- make `.` repeat plugin maps (abolish coercions, etc.)
  "abolish", -- case coercion (crs/crc/cru…) + case-preserving :S substitute
  "lazydev",
  "conform",
  "nvim-lint",
  "harpoon",
  "aerial", -- code outline / symbol tree sidebar — after treesitter + lspconfig
  "tiny-inline-diagnostic", -- inline diagnostic render (virtual_text off in config.lsp)
  "quicker", -- quickfix/loclist (replaces trouble)
  "grug-far", -- project-wide find & replace (editable buffer)
  "undotree", -- visual undo history navigator
  "sleuth", -- auto-detect shiftwidth/expandtab per buffer
  "obsidian",
  "markview",
  "dirtytalk", -- programming spellcheck dictionary (en + programming spelllang)
  "tiny-cmdline",
  "dap", -- DAP: nvim-dap + dap-ui + dap-python (deferred — no require until <leader>d)
}

local GITHUB = "https://github.com/"

local function to_url(src)
  if src:match("^%w[%w+.-]*://") or src:match("^git@") then
    return src
  end
  return GITHUB .. src
end

local function derive_name(src)
  return (src:gsub("%.git$", ""):match("([^/]+)$"))
end

-- name -> build hook, dispatched by the PackChanged autocmd below.
local build_hooks = {}

vim.api.nvim_create_autocmd("PackChanged", {
  group = vim.api.nvim_create_augroup("PackBuildHooks", { clear = true }),
  callback = function(ev)
    local d = ev.data
    if d.kind ~= "install" and d.kind ~= "update" then
      return
    end
    local hook = build_hooks[d.spec.name]
    if hook then
      local ok, err = pcall(hook, d)
      if not ok then
        vim.notify("pack build hook failed (" .. d.spec.name .. "): " .. tostring(err), vim.log.levels.ERROR)
      end
    end
  end,
})

local specs = {} -- flat list passed to vim.pack.add
local seen = {} -- dedupe by resolved name (so shared deps install once)
local declared = {} -- every plugin name the config knows about, INCLUDING
-- cond-skipped specs (e.g. obsidian outside ~/vault) and their deps. This is
-- the truth set for :PackClean — a plugin is stale only if it's absent here,
-- never merely because its cond was false this session.

local function declare(item)
  if type(item) == "string" then
    item = { src = item }
  end
  declared[item.name or derive_name(item.src)] = true
end

local function register(item)
  if type(item) == "string" then
    item = { src = item }
  end
  local name = item.name or derive_name(item.src)
  if seen[name] then
    return
  end
  seen[name] = true
  if item.build then
    build_hooks[name] = item.build
  end
  specs[#specs + 1] = { src = to_url(item.src), name = item.name, version = item.version }
end

local setups = {} -- { name, fn } in declared order

for _, modname in ipairs(plugin_order) do
  local mod = require("plugins." .. modname)
  -- A file returns a single spec (has .src) or a list of specs.
  local entries = mod.src and { mod } or mod
  for _, spec in ipairs(entries) do
    -- Record names for :PackClean regardless of cond, so a cond-gated plugin
    -- (and its deps) is never mistaken for an orphan when its cond is false.
    declare(spec)
    for _, dep in ipairs(spec.deps or {}) do
      declare(dep)
    end
    if spec.cond == nil or spec.cond() then
      for _, dep in ipairs(spec.deps or {}) do
        register(dep)
      end
      register(spec)
      if spec.setup then
        setups[#setups + 1] = { name = modname, fn = spec.setup }
      end
    end
  end
end

vim.pack.add(specs, { confirm = false })

for _, s in ipairs(setups) do
  local ok, err = pcall(s.fn)
  if not ok then
    vim.notify("plugin setup failed (" .. s.name .. "): " .. tostring(err), vim.log.levels.ERROR)
  end
end

require("config.lsp")

-- Convenience commands — lazy-style entry points over the vim.pack API.
local function plugin_names()
  return vim.tbl_map(function(p)
    return p.spec.name
  end, vim.pack.get())
end

-- :PackUpdate [name ...] — update everything, or just the named plugins. Opens
-- vim.pack's confirmation tabpage: :write applies, :quit discards. :restart
-- afterward to run the new code. Tab-completes installed plugin names.
vim.api.nvim_create_user_command("PackUpdate", function(opts)
  vim.pack.update(#opts.fargs > 0 and opts.fargs or nil)
end, {
  nargs = "*",
  desc = "Update vim.pack plugins (all, or named)",
  complete = function(arglead)
    return vim.tbl_filter(function(n)
      return n:find(arglead, 1, true) == 1
    end, plugin_names())
  end,
})

-- :PackStatus — browsable, offline (no fetch) view of installed plugins and
-- their pinned revisions. Navigate with [[ / ]], gO for an outline.
vim.api.nvim_create_user_command("PackStatus", function()
  vim.pack.update(nil, { offline = true })
end, { desc = "Review installed vim.pack plugins (offline)" })

-- :PackClean — delete plugins still on disk but no longer declared in the
-- config. Keyed off `declared` (not `p.active`) so cond-gated plugins like
-- obsidian aren't flagged just because their cond was false this session —
-- :PackClean is therefore safe to run from any cwd. Prompts before removing.
vim.api.nvim_create_user_command("PackClean", function()
  local stale = vim.tbl_map(
    function(p)
      return p.spec.name
    end,
    vim.tbl_filter(function(p)
      return not declared[p.spec.name]
    end, vim.pack.get())
  )

  if #stale == 0 then
    vim.notify("vim.pack: nothing to clean", vim.log.levels.INFO)
    return
  end

  vim.ui.select({ "yes", "no" }, {
    prompt = "Delete " .. #stale .. " unused plugin(s): " .. table.concat(stale, ", ") .. "?",
  }, function(choice)
    if choice == "yes" then
      vim.pack.del(stale)
    end
  end)
end, { desc = "Remove vim.pack plugins no longer in specs" })
