-- milli.nvim — animated ASCII/braille splashes, pure Lua (bundled splashes
-- need no binaries). The snacks dashboard plays one in its left pane via
-- util/dashboard.lua, which requires milli and so loads it on start.
-- :MilliPreview <name> to try a splash, :MilliBrowse for the community
-- registry. :MilliInstall is machine-local, so registry splashes the dashboard
-- uses are vendored into lua/milli/splashes/ instead.
return {
  "amansingh-afk/milli.nvim",
  lazy = true,
  cmd = { "MilliPreview", "MilliShader", "MilliScreensaver", "MilliInstall", "MilliUninstall", "MilliBrowse" },
}
