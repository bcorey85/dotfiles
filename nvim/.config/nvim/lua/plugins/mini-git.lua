return {
  {
    -- Sourced from the mini.nvim monorepo, NOT the standalone `echasnovski/mini.git`:
    -- the standalone's `.git` repo name collides with git's URL suffix convention
    -- (lazy builds `.../mini.git.git`, which GitHub resolves to a nonexistent `mini`
    -- repo → credential prompt). The monorepo ships the same `mini.git` module.
    "echasnovski/mini.nvim",
    event = "VeryLazy",
    config = function()
      require("mini.git").setup({})
    end,
  },
}
