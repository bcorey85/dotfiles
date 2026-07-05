-- mini.nvim — consolidated spec for all mini.* modules.
--
-- WHY ONE FILE: lazy.nvim merges specs that share a repo, and for same-repo
-- specs only ONE `config` survives the merge (event/ft/keys/deps merge, but
-- config is replaced). The old per-module files (mini-ai/surround/pairs/
-- indentscope/clue/icons) each had their own config, so under lazy they'd
-- clobber each other. They're merged here into a single config() instead.
--
-- LOADED EAGERLY (priority 100, below the colorscheme's 1000 but above snacks):
-- mini.icons installs the nvim-web-devicons mock that eager consumers (snacks,
-- winbar, oil) expect, so it must run before them. The other modules are cheap.
-- nvim-ts-autotag (separate repo) rides along below on a file event.
return {
  {
    "echasnovski/mini.nvim",
    lazy = false,
    priority = 100,
    dependencies = {
      -- mini.ai's gen_spec.treesitter needs the @function/@class/@parameter
      -- queries from textobjects (branch main). Also pulled by treesitter.lua.
      { "nvim-treesitter/nvim-treesitter-textobjects", branch = "main" },
    },
    config = function()
      -- ── mini.icons ─────────────────────────────────────────────────────────
      -- Shared icon provider; the mock lets plugins that require
      -- "nvim-web-devicons" (winbar, oil, markview) get mini.icons transparently.
      require("mini.icons").setup()
      MiniIcons.mock_nvim_web_devicons()

      -- ── mini.ai ────────────────────────────────────────────────────────────
      -- Extended text objects. Treesitter-backed f/c/a replace the removed
      -- treesitter-textobjects select maps (see treesitter.lua) so there's only
      -- one a/i handler and no timeout-ambiguity.
      local ai = require("mini.ai")
      local ts = ai.gen_spec.treesitter

      local function ts_safe(captures)
        local spec = ts(captures)
        return function(...)
          -- markdown_inline (and other langs without a textobjects query) make the
          -- treesitter spec throw E5108. Degrade to "no match" so a/i never errors.
          local ok, regions = pcall(spec, ...)
          return ok and regions or {}
        end
      end

      ai.setup({
        custom_textobjects = {
          f = ts_safe({ a = "@function.outer", i = "@function.inner" }),
          c = ts_safe({ a = "@class.outer", i = "@class.inner" }),
          a = ts_safe({ a = "@parameter.outer", i = "@parameter.inner" }),
        },
        n_lines = 50,
        search_method = "cover_or_next",
      })

      -- ── mini.surround ──────────────────────────────────────────────────────
      require("mini.surround").setup({
        mappings = {
          add = "gsa",
          delete = "gsd",
          find = "gsf",
          find_left = "gsF",
          highlight = "gsh",
          replace = "gsr",
          update_n_lines = "gsn",
        },
      })

      -- ── mini.pairs ─────────────────────────────────────────────────────────
      -- command-mode pairs are off: auto-inserting a closing )/}/] mid-pattern
      -- fights regex/substitution typing (:%s/(foo)/(bar)/, :g/{/). Insert mode
      -- keeps pairs; terminal stays off so they don't interfere with the shell.
      require("mini.pairs").setup({
        modes = { insert = true, command = false, terminal = false },
      })

      -- ── mini.indentscope ───────────────────────────────────────────────────
      -- Animation disabled — instant draw keeps the display snappy.
      local indentscope = require("mini.indentscope")
      indentscope.setup({
        symbol = "│",
        draw = {
          animation = indentscope.gen_animation.none(),
        },
        options = {
          try_as_border = true,
        },
      })
      vim.api.nvim_create_autocmd("FileType", {
        group = vim.api.nvim_create_augroup("MiniIndentscopeDisable", { clear = true }),
        pattern = {
          "checkhealth",
          "NeogitStatus",
          "git",
          "help",
          "lspinfo",
          "mason",
          "oil",
          "qf",
          "undotree",
        },
        callback = function()
          vim.b.miniindentscope_disable = true
        end,
      })

      -- ── mini.clue ──────────────────────────────────────────────────────────
      -- key-clue popup hints (replaced which-key). <C-w> resize submode via
      -- gen_clues.windows({ submode_resize = true }).
      local miniclue = require("mini.clue")
      miniclue.setup({
        triggers = {
          { mode = { "n", "x" }, keys = "<Leader>" },
          { mode = { "n", "x" }, keys = "g" },
          { mode = { "n", "x" }, keys = "'" },
          { mode = { "n", "x" }, keys = "`" },
          { mode = { "n", "x" }, keys = '"' },
          { mode = { "i", "c" }, keys = "<C-r>" },
          { mode = "n", keys = "<C-w>" },
          { mode = { "n", "x" }, keys = "z" },
          { mode = "n", keys = "[" },
          { mode = "n", keys = "]" },
        },

        clues = {
          miniclue.gen_clues.builtin_completion(),
          miniclue.gen_clues.g(),
          miniclue.gen_clues.marks(),
          miniclue.gen_clues.registers(),
          miniclue.gen_clues.windows({ submode_resize = true }),
          miniclue.gen_clues.z(),

          { mode = { "n", "x" }, keys = "<Leader>b", desc = "+buffer" },
          { mode = { "n", "x" }, keys = "<Leader>c", desc = "+changes" },
          { mode = { "n", "x" }, keys = "<Leader>f", desc = "+file/find" },
          { mode = { "n", "x" }, keys = "<Leader>g", desc = "+git" },
          { mode = { "n", "x" }, keys = "<Leader>gl", desc = "+list (forge)" },
          { mode = { "n", "x" }, keys = "<Leader>l", desc = "+lsp/quickfix" },
          { mode = { "n", "x" }, keys = "<Leader>n", desc = "+org" },
          { mode = { "n", "x" }, keys = "<Leader>N", desc = "+notes (obsidian)" },
          { mode = { "n", "x" }, keys = "<Leader>p", desc = "+project" },
          { mode = { "n", "x" }, keys = "<Leader>P", desc = "+plugins" },
          { mode = { "n", "x" }, keys = "<Leader>q", desc = "+quit/session" },
          { mode = { "n", "x" }, keys = "<Leader>s", desc = "+search" },
          { mode = { "n", "x" }, keys = "<Leader>t", desc = "+tasks" },
          { mode = { "n", "x" }, keys = "<Leader>T", desc = "+tabs" },
          { mode = { "n", "x" }, keys = "<Leader>u", desc = "+ui" },
          { mode = { "n", "x" }, keys = "<Leader>w", desc = "+windows" },
          { mode = { "n", "x" }, keys = "<Leader>y", desc = "+yank" },
          { mode = { "n", "x" }, keys = "g", desc = "+goto" },
          { mode = "n", keys = "[", desc = "+prev" },
          { mode = "n", keys = "]", desc = "+next" },
        },

        window = {
          delay = 300,
          config = { width = "auto" },
        },
      })
    end,
  },

  -- nvim-ts-autotag — auto-close/rename HTML & JSX tags (was in mini-pairs.lua).
  {
    "windwp/nvim-ts-autotag",
    event = { "BufReadPost", "BufNewFile" },
    config = function()
      require("nvim-ts-autotag").setup({})
    end,
  },
}
