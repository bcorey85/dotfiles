-- Loaded eagerly (it's listed early in pack.lua's plugin_order) because the
-- winbar (lua/config/winbar.lua) renders a file icon on every window and needs
-- the icon table available from the first buffer. Also the shared icon provider
-- for oil and render-markdown. No setup() needed — the module auto-initializes
-- its default icon set on first require.
return {
  src = "nvim-tree/nvim-web-devicons",
}
