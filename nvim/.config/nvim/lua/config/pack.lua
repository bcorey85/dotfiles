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
local plugin_order = {
  "theme", -- colorscheme — must be first
  "web-devicons", -- icon table (winbar + others) — before consumers
  "treesitter", -- before render-markdown / mini.ai textobjects
  "lspconfig", -- ships lsp/ server defs consumed by config.lsp
  "mason", -- LSP / tool installer (3 plugins)
  "blink", -- completion
  "telescope", -- finder (+ plenary / fzf-native / ui-select)
  "oil",
  "smart-splits",
  "gitsigns",
  "fugitive",
  "mini-ai",
  "mini-surround",
  "mini-bufremove",
  "autoclose",
  "flash",
  "which-key",
  "ts-comments",
  "lazydev",
  "conform",
  "nvim-lint",
  "harpoon",
  "grug-far",
  "trouble",
  "gitlinker",
  "obsidian",
  "render-markdown",
  "tiny-cmdline",
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

-- :PackClean — delete plugins still on disk but no longer in your specs (not
-- added this session). Prompts before removing.
vim.api.nvim_create_user_command("PackClean", function()
  local stale = vim.tbl_map(function(p)
    return p.spec.name
  end, vim.tbl_filter(function(p)
    return not p.active
  end, vim.pack.get()))

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
