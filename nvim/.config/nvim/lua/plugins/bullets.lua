-- bullets.vim — list continuation in markdown/text/gitcommit: <CR> or o on a
-- bullet, numbered or checkbox line starts the next item at the same indent;
-- <C-t>/<C-d> in insert indent/outdent it. <CR> on an empty item removes it
-- (mode 2, Obsidian-style: outdent first, then delete at the top level).
-- No clash with blink's super-tab preset, which leaves <CR> alone.
return {
  "bullets-vim/bullets.vim",
  ft = { "markdown", "text", "gitcommit" },
  init = function()
    vim.g.bullets_enabled_file_types = { "markdown", "text", "gitcommit" }
    -- off in nameless scratch buffers, so pickers' prompt buffers keep <CR>
    vim.g.bullets_enable_in_empty_buffers = 0
    vim.g.bullets_delete_last_bullet_if_empty = 2
  end,
}
