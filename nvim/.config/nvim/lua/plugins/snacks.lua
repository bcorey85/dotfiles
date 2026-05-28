local exclude = {
  "node_modules",
  "dist",
  "build",
  "__pycache__",
  ".venv",
  "*.pyc",
  ".mypy_cache",
  ".ruff_cache",
  "staticfiles",
  "media",
  "*.sqlite3",
  ".git",
  ".nuxt",
}

return {
  "folke/snacks.nvim",
  priority = 1000,
  lazy = false,
  opts = {
    bigfile = { enabled = true },
    -- Skip the dashboard in the Diffview review popup (tmux `prefix d`, which
    -- sets DIFFVIEW_POPUP). Otherwise it opens on startup and `prefix d` shows
    -- the dashboard before diffview, needing a second `q` to dismiss. Stays
    -- enabled for normal nvim (env var unset).
    dashboard = { enabled = vim.env.DIFFVIEW_POPUP == nil },
    explorer = { enabled = false },
    indent = { enabled = true },
    input = { enabled = true },
    notifier = {
      enabled = true,
      timeout = 3000,
    },
    picker = {
      enabled = true,
      sources = {
        explorer = {
          hidden = true,
          ignored = true,
          exclude = { ".git" },
          watcher = true,
        },
        files = {
          hidden = true,
          ignored = false,
          follow = true,
          exclude = exclude,
        },
        grep = {
          hidden = true,
          ignored = false,
          follow = true,
          exclude = exclude,
        },
      },
    },
    quickfile = { enabled = true },
    scope = { enabled = true },
    scroll = { enabled = false },
    statuscolumn = { enabled = false },
    words = { enabled = true },
    lazygit = { enabled = true },
    styles = {
      notification = {},
    },
  },
  keys = {
    { "<leader><space>", function() Snacks.picker.smart() end, desc = "Smart Find Files" },
    { "<leader>,", function() Snacks.picker.buffers() end, desc = "Buffers" },
    { "<leader>/", function() Snacks.picker.grep() end, desc = "Grep" },
    { "<leader>ff", function() Snacks.picker.files() end, desc = "Find files" },
    { "<leader>fr", function() Snacks.picker.recent() end, desc = "Recent files" },
    { "<leader>fg", function() Snacks.picker.grep() end, desc = "Grep" },
    { "<leader>fb", function() Snacks.picker.buffers() end, desc = "Buffers" },
    { "<leader>fh", function() Snacks.picker.help() end, desc = "Help pages" },
    { "<leader>fk", function() Snacks.picker.keymaps() end, desc = "Keymaps" },
    { "<leader>fc", function() Snacks.picker.command_history() end, desc = "Command history" },
    { "<leader>fo", function() Snacks.picker.colorschemes() end, desc = "Colorschemes" },
    {
      "<leader>fI",
      function() Snacks.picker.files({ hidden = true, ignored = true }) end,
      desc = "Find files (including ignored)",
    },
    {
      "<leader>gs",
      function() Snacks.picker.git_status({ layout = "sidebar" }) end,
      desc = "Git Status (sidebar)",
    },
    {
      "<leader>gg",
      function()
        local in_tmux = vim.env.TMUX ~= nil
        if in_tmux then
          local zoomed = vim.fn.system("tmux display-message -p '#{window_zoomed_flag}'"):gsub("%s+", "")
          if zoomed ~= "1" then
            vim.fn.system("tmux resize-pane -Z")
          end
        end
        Snacks.lazygit({
          win = {
            width = 0.99,
            height = 0.99,
            on_close = function()
              if in_tmux then
                local zoomed = vim.fn.system("tmux display-message -p '#{window_zoomed_flag}'"):gsub("%s+", "")
                if zoomed == "1" then
                  vim.fn.system("tmux resize-pane -Z")
                end
              end
            end,
          },
        })
      end,
      desc = "Lazygit (zoomed)",
    },
    { "<leader>sd", function() Snacks.picker.diagnostics() end, desc = "Diagnostics" },
    { "<leader>ss", function() Snacks.picker.lsp_symbols() end, desc = "LSP symbols" },
    { "<leader>sw", function() Snacks.picker.grep_word() end, desc = "Grep word under cursor" },
  },
}
