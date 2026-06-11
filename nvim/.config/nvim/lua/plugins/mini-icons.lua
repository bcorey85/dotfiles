-- mini.icons replaces nvim-web-devicons as the shared icon provider.
-- MiniIcons.mock_nvim_web_devicons() installs a compatibility shim so that
-- plugins requiring "nvim-web-devicons" (winbar, oil, render-markdown) get the
-- mini.icons implementation transparently — no changes needed in consumers.
-- Listed early in plugin_order (before its consumers) so the mock is in place
-- before any plugin's setup() fires.
return {
  src = "echasnovski/mini.nvim",
  setup = function()
    require("mini.icons").setup()
    MiniIcons.mock_nvim_web_devicons()
  end,
}
