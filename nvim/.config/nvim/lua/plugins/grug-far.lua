return {
  src = "MagicDuck/grug-far.nvim",
  -- Deferred: nothing from grug-far is required until the first <leader>sr. The
  -- plugin is on the runtimepath (so :PackUpdate manages it), but setup() only
  -- runs on first use — keeping its Lua require off the startup path.
  setup = function()
    local configured = false
    vim.keymap.set("n", "<leader>sr", function()
      if not configured then
        require("grug-far").setup({ headerMaxWidth = 80 })
        configured = true
      end
      require("grug-far").open()
    end, { desc = "Search and Replace" })
  end,
}
