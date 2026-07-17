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
  "brianhuster/live-preview.nvim",
  -- Load on ft (NOT keys): <leader>mm is a BUFFER-LOCAL map set by the FileType
  -- autocmd below. A keys trigger would never fire that autocmd (the plugin
  -- wouldn't load until the key is pressed, by which point FileType is long
  -- gone), so the buffer-local map would never exist. ft loads it when a
  -- preview-able buffer opens; lazy re-emits FileType so the autocmd runs.
  ft = { "markdown", "html", "asciidoc", "svg" },
  cmd = { "LivePreview" },
  config = function()
    -- Every nvim instance defaults to port 5500, so a second instance collides
    -- with the first (which still holds it) — the plugin only warns, then binds
    -- anyway and the preview silently breaks. Ask the OS for a free ephemeral
    -- port per instance (bind to :0, read the assignment, release it) so
    -- instances never fight over one port. Falls back to 5500 if the probe fails.
    local function free_port()
      local sock = vim.uv.new_tcp()
      if not sock then
        return 5500
      end
      local ok = pcall(function()
        assert(sock:bind("127.0.0.1", 0))
      end)
      local port = 5500
      if ok then
        local addr = sock:getsockname()
        if addr and addr.port then
          port = addr.port
        end
      end
      sock:close()
      return port
    end

    require("livepreview").setup({
      -- Use the snacks picker (already installed) for `:LivePreview pick`.
      picker = "snacks.picker",
      port = free_port(), -- per-instance free port; see free_port() above
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
