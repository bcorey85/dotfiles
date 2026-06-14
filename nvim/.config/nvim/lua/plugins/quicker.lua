-- quicker.nvim — editable quickfix/loclist with context expansion.
-- Replaces trouble.nvim: native qf/loclist windows, no extra UI layer.
-- cfilter (`:Cfilter`/`:Lfilter`) ships with Neovim and is loaded here
-- since this is the natural home for quickfix tooling.
return {
  src = "stevearc/quicker.nvim",
  setup = function()
    -- cfilter ships with Neovim; enables :Cfilter/:Lfilter to narrow qf/loclist by pattern.
    vim.cmd.packadd("cfilter")

    require("quicker").setup({
      keys = {
        {
          ">",
          function()
            require("quicker").expand({ before = 2, after = 2, add_to_existing = true })
          end,
          desc = "Expand quickfix context",
        },
        {
          "<",
          function()
            require("quicker").collapse()
          end,
          desc = "Collapse quickfix context",
        },
      },
    })

    local map = function(lhs, rhs, desc)
      vim.keymap.set("n", lhs, rhs, { desc = desc })
    end

    map("<leader>ld", function()
      vim.diagnostic.setqflist({ open = true })
    end, "Diagnostics → quickfix (workspace)")
    map("<leader>lD", function()
      vim.diagnostic.setloclist({ open = true })
    end, "Diagnostics → loclist (buffer)")
    map("<leader>lq", function()
      require("quicker").toggle()
    end, "Quickfix (toggle)")
    map("<leader>lL", function()
      require("quicker").toggle({ loclist = true })
    end, "Loclist (toggle)")

    -- When stepping the repo-wide hunk qf list (<leader>cq, titled "Gitsigns
    -- Hunks"), show that hunk's diff inline on arrival so you can eyeball the
    -- change before staging — no preview split needed. preview_hunk_inline
    -- clears itself on the next CursorMoved, so the following ]q wipes it.
    -- Title-gated: ordinary grep/diagnostic qf navigation is unaffected.
    --
    -- The wrinkle: :cnext into a file you haven't opened loads it cold, and
    -- gitsigns attaches + computes hunks ASYNCHRONOUSLY (it spawns git). A fixed
    -- delay is a guess. Instead: if the buffer is already attached, preview now;
    -- otherwise wait for gitsigns' own "User GitSignsUpdate" (it carries the
    -- buffer in data.buffer) and preview the moment hunks land. A monotonic
    -- token means a fast second ]q supersedes a still-pending preview.
    local pending = 0

    local function show_inline(bufnr, token)
      if token ~= pending or vim.api.nvim_get_current_buf() ~= bufnr then
        return
      end
      local ok, gs = pcall(require, "gitsigns")
      if ok then
        pcall(gs.preview_hunk_inline)
      end
    end

    local function preview_hunk_if_list()
      if vim.fn.getqflist({ title = 0 }).title ~= "Gitsigns Hunks" then
        return
      end
      local bufnr = vim.api.nvim_get_current_buf()
      pending = pending + 1
      local token = pending

      local cache = package.loaded["gitsigns.cache"]
      if cache and cache.cache[bufnr] then
        -- Already attached (revisited file) — no update event will fire, so go now.
        vim.schedule(function()
          show_inline(bufnr, token)
        end)
        return
      end

      -- Cold buffer: fire once gitsigns reports hunks for it. Returning true from
      -- the callback deletes the autocmd (when matched, or once superseded).
      vim.api.nvim_create_autocmd("User", {
        pattern = "GitSignsUpdate",
        callback = function(ev)
          if token ~= pending then
            return true
          end
          if ev.data and ev.data.buffer == bufnr then
            show_inline(bufnr, token)
            return true
          end
        end,
      })
    end

    map("[q", function()
      if pcall(vim.cmd.cprev) then
        preview_hunk_if_list()
      else
        vim.notify("No previous quickfix item", vim.log.levels.WARN)
      end
    end, "Previous quickfix item")
    map("]q", function()
      if pcall(vim.cmd.cnext) then
        preview_hunk_if_list()
      else
        vim.notify("No next quickfix item", vim.log.levels.WARN)
      end
    end, "Next quickfix item")
  end,
}
