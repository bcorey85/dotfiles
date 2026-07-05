-- Byte-compile cache for faster require() — introduced in Neovim 0.9, not
-- enabled by default even in 0.12. The guard makes this a no-op on older
-- builds (0.10/0.11) and on builds where the field doesn't exist yet.
if vim.loader and not vim.loader.enabled then
  vim.loader.enable()
end

require("config.options")
require("config.winbar")
require("config.autocmds")
require("config.keymaps")
require("config.review")
require("config.ui-input")
require("config.lazy")
