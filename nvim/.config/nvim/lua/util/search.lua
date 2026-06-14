-- Single source of truth for search exclusions, shared by every search surface:
-- the snacks.picker grep/files pickers (plugins/snacks.lua) and the :grep
-- grepprg (config/options.lua). Moved out of the old mini-pick.lua so the
-- exclusion intent survives the picker swap with one definition, not three.

local M = {}

-- Junk dirs excluded at ANY depth: caches, build output, deps. Never worth
-- searching wherever they sit.
M.excluded_dirs = {
  ".git",
  "node_modules",
  ".venv",
  "venv",
  "__pycache__",
  "dist",
  "build",
  ".next",
  "target",
  "coverage",
  ".cache",
  ".pytest_cache",
  ".mypy_cache",
  ".ruff_cache",
  "htmlcov",
  "COMPRESS_CACHE",
}

-- Junk dirs excluded only at the REPO ROOT. Names like static/ and media/ are
-- generated/collected asset trees at the project root (Django collectstatic,
-- user uploads) — huge and pointless to search — but are often real source when
-- nested (app/static/, frontend/**/static/). Root-anchoring ("/<dir>/**") kills
-- the big generated trees without hiding nested source.
M.excluded_root_dirs = {
  "static",
  "staticfiles",
  "media",
  "media_files",
}

-- Bare exclusion glob patterns (NO leading "!"): depth dirs anchored at any
-- level ("**/<dir>/**"), asset dirs anchored at the search root ("/<dir>/**").
-- snacks.picker's `exclude` opt consumes these directly — it adds the rg `!`
-- (`-g !<pat>`) or fd `-E <pat>` wrapper itself. grepprg wraps each as
-- `--glob='!<pat>'`. Root-anchoring ("/…") only takes effect under rg (grep
-- picker + grepprg); fd ignores the anchor, which matches the old config.
function M.exclude_patterns()
  local pats = {}
  for _, dir in ipairs(M.excluded_dirs) do
    table.insert(pats, "**/" .. dir .. "/**")
  end
  for _, dir in ipairs(M.excluded_root_dirs) do
    table.insert(pats, "/" .. dir .. "/**")
  end
  return pats
end

return M
