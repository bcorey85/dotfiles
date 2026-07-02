-- live-preview.nvim — browser markdown/html/asciidoc/svg preview with live
-- updates AS YOU TYPE. Replaced iamcco/markdown-preview.nvim, which relied on a
-- Node/yarn build + a save-triggered websocket that constantly went stale and
-- stopped updating. This backend is pure Lua (Neovim's built-in server/uv), so
-- there's no external runtime to install (fits the apt/brew/pacman-only rule)
-- and no build step to break. Needs only a browser. Nvim >= 0.10.1.
--
-- Config lives in require("livepreview").setup(); commands are
-- `:LivePreview start|close|pick|help` (no built-in toggle — see the bind).
return {
  src = "brianhuster/live-preview.nvim",
  setup = function()
    require("livepreview").setup({
      -- Use the snacks picker (already installed) for `:LivePreview pick`.
      picker = "snacks.picker",
      sync_scroll = true, -- browser follows the cursor as you scroll in nvim
    })

    -- Single toggle bind, buffer-local to preview-able filetypes so it never
    -- collides with orgmode's <leader>m localleader (org buffers) or the
    -- mini.clue <leader>m group. is_running() reads the real server state, so
    -- one key reliably flips open/closed without a self-tracked flag drifting.
    vim.api.nvim_create_autocmd("FileType", {
      pattern = { "markdown", "html", "asciidoc", "svg" },
      group = vim.api.nvim_create_augroup("LivePreviewKeys", { clear = true }),
      callback = function(ev)
        vim.keymap.set("n", "<leader>mm", function()
          if require("livepreview").is_running() then
            vim.cmd("LivePreview close")
          else
            vim.cmd("LivePreview start")
          end
        end, { buffer = ev.buf, desc = "Markdown preview (toggle in browser)" })
      end,
    })
  end,
}
