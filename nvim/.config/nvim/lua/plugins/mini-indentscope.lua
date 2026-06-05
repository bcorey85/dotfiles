-- mini.indentscope: animated vertical line marking the current indent scope.
--
-- snacks.indent's own `scope` is disabled (snacks.lua) so the two don't both draw
-- the active scope. snacks still draws the faint all-level indent guides;
-- mini.indentscope adds the animated current-scope line + [i / ]i motions.
--
-- The `ai`/`ii` indent textobjects are intentionally disabled: mini.ai owns the
-- a/i namespace and would clobber a 2-char `ai`/`ii` mapping. Only goto kept.
return {
  "echasnovski/mini.indentscope",
  event = { "BufReadPost", "BufNewFile" },
  config = function()
    require("mini.indentscope").setup({
      symbol = "│",
      mappings = {
        object_scope = "",
        object_scope_with_border = "",
        goto_top = "[i",
        goto_bottom = "]i",
      },
    })

    -- Don't draw the scope line in non-code / UI buffers.
    vim.api.nvim_create_autocmd("FileType", {
      pattern = {
        "help",
        "snacks_dashboard",
        "lazy",
        "mason",
        "oil",
        "Trouble",
        "trouble",
        "neo-tree",
        "NeogitStatus",
      },
      callback = function()
        vim.b.miniindentscope_disable = true
      end,
    })
  end,
}
