-- octo.nvim — GitHub issues & PRs as editable buffers (the nvim port of Emacs
-- forge). Uses the Snacks picker (matches the rest of the config) and the gh
-- CLI (already authenticated for <leader>gr). plenary is shared with harpoon;
-- nvim-web-devicons is satisfied by mini.icons' mock (see mini-icons.lua).
--
-- Keymaps mirror Doom's forge layout under SPC g:
--   <leader>gl i/p/n  → issue / pr / notification list   (Doom `SPC g l …`)
--   <leader>g'        → octo actions palette             (Doom `SPC g '` dispatch)
-- In-PR review keys (comment / approve / thread nav) are buffer-local — octo
-- binds them automatically when a PR or review buffer opens.
return {
  src = "pwntester/octo.nvim",
  deps = { "nvim-lua/plenary.nvim" },
  setup = function()
    require("octo").setup({ picker = "snacks" })

    local map = function(lhs, rhs, desc)
      vim.keymap.set("n", lhs, rhs, { desc = desc })
    end

    map("<leader>gli", "<cmd>Octo issue list<cr>", "Issues (list)")
    map("<leader>glp", "<cmd>Octo pr list<cr>", "PRs (list)")
    -- Snacks picker support for notifications is still pending upstream
    -- (octo.nvim#1232); mapped for Doom parity, may no-op until it ships.
    map("<leader>gln", "<cmd>Octo notification list<cr>", "Notifications (list)")
    map("<leader>g'", "<cmd>Octo actions<cr>", "Octo actions")
  end,
}
