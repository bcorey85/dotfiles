-- mini.indentscope: animated vertical line marking the current indent scope.
--
-- mini.indentscope draws the active-scope line; there are no longer all-level
-- indent guides. Adds the animated current-scope line + [i / ]i motions.
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
