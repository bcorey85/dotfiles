-- mini.ai: extended text objects with seeking, brackets, quotes, tags, etc.
-- Sourced from the mini.nvim monorepo (shared clone).
--
-- WHY: nvim-treesitter-textobjects' select module (af/if/ac/ic/aa/ia) creates
-- timeout-ambiguity on every a/i keystroke because mini.ai owns that namespace.
-- The fix is to route the same captures through mini.ai's custom_textobjects so
-- there is only one a/i handler. The 6 select keymaps in treesitter.lua are
-- removed there; the MOVE maps (]f/[f/]C/[C) are left alone — they don't conflict.
--
-- DEPENDENCY: nvim-treesitter-textobjects (branch main) must be present for
-- gen_spec.treesitter to find the @function/@class/@parameter queries. It's
-- already pulled in by treesitter.lua; listed here too so the dep is explicit.
return {
  src = "echasnovski/mini.nvim",
  deps = {
    { src = "nvim-treesitter/nvim-treesitter-textobjects", version = "main" },
  },
  setup = function()
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
        -- Treesitter-backed replacements for the removed treesitter-textobjects
        -- select maps. Keys match what the user already knows: f=function,
        -- c=class, a=argument/parameter (so aa/ia works unchanged).
        f = ts_safe({ a = "@function.outer", i = "@function.inner" }),
        c = ts_safe({ a = "@class.outer", i = "@class.inner" }),
        a = ts_safe({ a = "@parameter.outer", i = "@parameter.inner" }),
      },
      -- n_lines controls how far mini.ai seeks for text objects;
      -- 50 is the default and sufficient for most function bodies.
      n_lines = 50,
      search_method = "cover_or_next",
    })
  end,
}
