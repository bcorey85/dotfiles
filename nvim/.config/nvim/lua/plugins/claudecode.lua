-- claudecode.nvim — IDE/MCP bridge between nvim and the Claude Code CLI.
-- Closes the parity gap with Doom's claude-code-ide: Claude sees the current
-- selection / attached files, and proposed edits open as native nvim diffs you
-- accept/reject in the editor instead of eyeballing terminal renders.
--
-- How it connects (the dev-layout claude pane is unchanged):
--   1. On startup this plugin starts a WebSocket server and writes a lock file
--      to ~/.claude/ide/<port>.lock.
--   2. In the existing claude pane (same project cwd), run `/ide` and pick
--      Neovim. Selections, @-mentions, and diff review then flow both ways.
-- :ClaudeCode can also spawn the pane when none exists — the external provider
-- below splits 40% right via tmux, mirroring the `dev` layout.
--
-- Keymaps — extends the <leader>c claude cluster (cc/cp in config/review.lua):
--   <leader>ca  v: send selection · n: add current buffer · oil: add file
--   <leader>cy  accept Claude's proposed diff   ("claude yes")
--   <leader>cd  reject Claude's proposed diff   ("claude deny")
return {
  "coder/claudecode.nvim",
  keys = {
    { "<leader>ca", mode = { "n", "v" }, desc = "Claude: add buffer / send selection" },
    { "<leader>cy", desc = "Claude: accept diff" },
    { "<leader>cd", desc = "Claude: reject diff" },
  },
  config = function()
    require("claudecode").setup({
      terminal = {
        provider = "external",
        provider_opts = {
          -- first %s = cwd, second %s = the claude command
          external_terminal_cmd = "tmux split-window -h -p 40 -c %s %s",
        },
      },
    })

    local map = vim.keymap.set
    map("v", "<leader>ca", "<cmd>ClaudeCodeSend<cr>", { desc = "Claude: send selection" })
    map("n", "<leader>ca", "<cmd>ClaudeCodeAdd %<cr>", { desc = "Claude: add buffer to context" })
    map("n", "<leader>cy", "<cmd>ClaudeCodeDiffAccept<cr>", { desc = "Claude: accept diff" })
    map("n", "<leader>cd", "<cmd>ClaudeCodeDiffDeny<cr>", { desc = "Claude: reject diff" })

    -- In oil buffers, <leader>ca attaches the file under the cursor (not the
    -- oil buffer itself).
    vim.api.nvim_create_autocmd("FileType", {
      pattern = "oil",
      group = vim.api.nvim_create_augroup("ClaudeCodeOil", { clear = true }),
      callback = function(ev)
        vim.keymap.set(
          "n",
          "<leader>ca",
          "<cmd>ClaudeCodeTreeAdd<cr>",
          { buffer = ev.buf, desc = "Claude: add file under cursor" }
        )
      end,
    })
  end,
}
