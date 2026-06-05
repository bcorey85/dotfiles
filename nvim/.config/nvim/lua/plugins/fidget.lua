-- fidget: LSP progress spinner (bottom-right, updates in place). Fills the gap
-- left by noice's lsp.progress being disabled and snacks not doing progress.
--
-- Notifications stay with snacks.notifier: fidget's notification backend is told
-- NOT to take over vim.notify, so the two don't fight over toasts.
return {
  "j-hui/fidget.nvim",
  event = "LspAttach",
  opts = {
    notification = {
      override_vim_notify = false,
    },
  },
}
