-- theme-sync — keep nvim in sync with the shared theme state written by the
-- `theme-mode` script (scripts/.local/bin/theme-mode):
--   ~/.cache/theme-mode    "dark" | "light"
--   ~/.cache/theme-family  family name (FAMILIES below)
-- Both files are fs_poll'ed (~1s), so `theme-mode use one` or a prefix T
-- toggle from herdr flips every running instance with no sockets to manage.
-- <leader>ut shells out to the same script, so a toggle from nvim flips herdr
-- and ghostty too — one source of truth, all ways.
--
-- This module also owns every theme-reactive highlight override (markdown
-- headings, gitsigns word-diff), re-applied on ColorScheme,
-- so a family switch always lands with the right set. Plugin specs stay pure
-- plugin declarations. Keep FAMILIES in sync with theme-mode's registry and
-- the ghostty/herdr theme files.

local M = {}

local MODE_FILE = vim.env.HOME .. "/.cache/theme-mode"
local FAMILY_FILE = vim.env.HOME .. "/.cache/theme-family"
local DEFAULT_FAMILY = "onedarkpro"

-- alpha-blend two hex colours (a = share of c1).
local function blend(c1, c2, a)
  local out = {}
  for i = 2, 6, 2 do
    local v = tonumber(c1:sub(i, i + 1), 16) * a + tonumber(c2:sub(i, i + 1), 16) * (1 - a)
    out[#out + 1] = string.format("%02x", math.floor(v + 0.5))
  end
  return "#" .. table.concat(out)
end

-- Registry shape: the mode axis and the state-file plumbing both key off this table — adding a family is an entry here plus theme-mode's
-- cases and the ghostty/herdr files.
local FAMILIES = {
  ["bamboo"] = {
    -- ribru17/bamboo.nvim: one colorscheme "bamboo" picks its style from
    -- vim.o.background (light palette #fafae0 / vulgaris #252623) and always
    -- sets colors_name to "bamboo", so both are pinned here.
    schemes = { dark = "bamboo", light = "bamboo" },
    colors_name = "bamboo",
    -- bamboo paints markdown headings from its own rainbow blends: H1 =
    -- blend(red, inverse, 0.25), H2 = blend(orange, inverse, 0.25).
    accents = {
      dark = { heading1 = "#ed839d", heading = "#ffb38c" },
      light = { heading1 = "#95202d", heading = "#a7431d" },
    },
  },
  ["gruvbox-material"] = {
    -- sainnhe/gruvbox-material, HARD background, foreground = "original" — the
    -- ORIGINAL gruvbox accents (red #fb4934, fg #ebdbb2) over hard grounds
    -- (#1d2021 dark / #f9f5d7 light, a stop past gruvbox's medium #282828 /
    -- #fbf1c7) and material's own role table (Function green, Operator orange,
    -- Constant aqua, PreProc purple). One colorscheme follows
    -- vim.o.background and sets colors_name "gruvbox-material" in both modes.
    schemes = { dark = "gruvbox-material", light = "gruvbox-material" },
    colors_name = "gruvbox-material",
    -- The variant globals are read at :colorscheme time, hence `pre`.
    pre = function()
      vim.g.gruvbox_material_background = "hard"
      vim.g.gruvbox_material_foreground = "original"
    end,
    accents = {
      dark = { heading1 = "#fb4934", heading = "#fabd2f" }, -- red + yellow
      light = { heading1 = "#9d0006", heading = "#b57614" },
    },
  },
  ["edge"] = {
    schemes = { dark = "edge", light = "edge" },
    colors_name = "edge",
    pre = function()
      vim.g.edge_style = "aura"
    end,
    accents = {
      dark = { heading1 = "#ec7279", heading = "#deb974" },
      light = { heading1 = "#c93f3f", heading = "#9a6604" },
    },
  },
  ["tokyonight"] = {
    -- folke/tokyonight.nvim storm #24283b / day #e1e2e7.
    schemes = { dark = "tokyonight-storm", light = "tokyonight-day" },
    accents = {
      dark = { heading1 = "#f7768e", heading = "#e0af68" },
      light = { heading1 = "#f52a65", heading = "#8c6c3e" },
    },
  },
  ["onedarkpro"] = {
    schemes = { dark = "onedark", light = "onelight" },
    accents = {
      dark = { heading1 = "#e06c75", heading = "#e5c07b" },
      light = { heading1 = "#e05661", heading = "#eea825" },
    },
  },
  ["dracula"] = {
    schemes = { dark = "dracula", light = "alucard" },
    accents = {
      dark = { heading1 = "#FF79C6", heading = "#BD93F9" },
      light = { heading1 = "#A3144D", heading = "#644AC9" },
    },
  },
  ["nightfox"] = {
    schemes = { dark = "nightfox", light = "dayfox" },
    accents = {
      dark = { heading1 = "#c94f6d", heading = "#dbc074" },
      light = { heading1 = "#a5222f", heading = "#AC5402" },
    },
  },
  ["duskfox"] = {
    schemes = { dark = "duskfox", light = "dawnfox" },
    accents = {
      dark = { heading1 = "#eb6f92", heading = "#f6c177" },
      light = { heading1 = "#b4637a", heading = "#ea9d34" },
    },
  },
  ["dredge"] = {
    schemes = { dark = "dredge", light = "dredge" },
    colors_name = "dredge",
    accents = {
      dark = { heading1 = "#9a99f3", heading = "#86beee" },
      light = { heading1 = "#9a99f3", heading = "#86beee" },
    },
  },
}

local applied ---@type string|nil  last family+mode we set, to skip redundant reloads

-- Read a state file's first line, trimmed; nil if missing.
local function read_state(path)
  local f = io.open(path, "r")
  if not f then
    return nil
  end
  local raw = f:read("l") or ""
  f:close()
  return (raw:gsub("%s+", ""))
end

local function normalize_mode(mode)
  return mode == "light" and "light" or "dark"
end

local function normalize_family(family)
  return FAMILIES[family] and family or DEFAULT_FAMILY
end

function M.read_state()
  return normalize_family(read_state(FAMILY_FILE)), normalize_mode(read_state(MODE_FILE))
end

-- Markdown heading + bullet colours. touchup.nvim renders no heading icons and
-- defines no heading hl of its own, so headings fall back to native treesitter
-- highlighting — we paint @markup.heading.N.markdown directly (most specific,
-- so it wins over the family scheme and over touchup's default underline). H1
-- gets the accent, H2–H6 the muted heading colour, matching the old MdHeading*.
-- Bullets: touchup keys bullet hl by marker char, so tint all three groups.
local function set_headings(a)
  local hl = vim.api.nvim_set_hl
  hl(0, "@markup.heading.1.markdown", { fg = a.heading1, bold = true })
  for i = 2, 6 do
    hl(0, "@markup.heading." .. i .. ".markdown", { fg = a.heading, bold = true })
  end
  for _, g in ipairs({ "TouchupBulletDash", "TouchupBulletPlus", "TouchupBulletStar" }) do
    hl(0, g, { fg = a.heading })
  end
end

-- Prose reading calm. Treesitter's markdown_inline/markdown parsers paint each
-- markup kind its own hue (bold/italic pink, code green, quote pink, links
-- lavender, bullets teal), so a single paragraph turns into five competing
-- colours — the "too busy to read prose" complaint. Strip the COLOUR and keep
-- the SIGNAL: bold stays bold, italic stays slanted, links keep an underline,
-- the raw URL and list markers drop to muted. Scoped to the language-specific
-- groups (.markdown_inline / .markdown) so only markdown is calmed — @markup.*
-- in help/other langs keeps its scheme colours. Theme-agnostic (weight/underline
-- + links to Normal/Comment), so it tracks every family/mode switch.
--
-- Inline code follows github.com: body fg on a faint chip, never a hue. Most
-- schemes paint `code` a syntax colour (and @markup.raw ships italic), which
-- makes a sentence with three backticked paths read as three different kinds of
-- thing. The chip is Normal fg blended 12% into Normal bg, so it lands one step
-- off the canvas in either mode without hardcoding a palette.
local function set_prose()
  local hl = vim.api.nvim_set_hl
  local n = vim.api.nvim_get_hl(0, { name = "Normal", link = false })
  local fg = n.fg and string.format("#%06x", n.fg)
  local bg = n.bg and string.format("#%06x", n.bg)
  local rules = {
    ["@markup.strong.markdown_inline"] = { bold = true },
    ["@markup.italic.markdown_inline"] = { italic = true },
    ["@markup.quote.markdown"] = { italic = true },
    ["@markup.link.markdown_inline"] = { underline = true },
    ["@markup.link.label.markdown_inline"] = { underline = true },
    ["@markup.link.url.markdown_inline"] = { link = "Comment" },
    ["@markup.list.markdown"] = { link = "Comment" },
  }
  if fg and bg then
    rules["@markup.raw.markdown_inline"] = { fg = fg, bg = blend(fg, bg, 0.12) }
  end
  for group, spec in pairs(rules) do
    hl(0, group, spec)
  end
end

-- gitsigns word-diff readability (the `=` whole-file inline overlay, keymaps.lua).
-- gitsigns' inline word-diff groups (GitSigns{Change,Add,Delete}LnInline)
-- default to `reverse = true`, which paints dim token fgs (comments worst)
-- as unreadable blocks. Replace reverse with the theme's own diff
-- backgrounds + a forced bright Normal fg, so the emphasised word reads on
-- ANY underlying token. Reads the resolved palette at ColorScheme time, so
-- it is theme-agnostic and tracks every family/mode switch.
local function set_word_diff()
  local hl = vim.api.nvim_set_hl
  local function bg_of(name)
    return vim.api.nvim_get_hl(0, { name = name, link = false }).bg
  end
  local fg = vim.api.nvim_get_hl(0, { name = "Normal", link = false }).fg
  -- DiffText (word-emphasis) sits a shade lighter than DiffChange (the
  -- line bg), so the changed word still pops out of its own changed line.
  hl(0, "GitSignsChangeLnInline", { fg = fg, bg = bg_of("DiffText"), bold = true })
  hl(0, "GitSignsAddLnInline", { fg = fg, bg = bg_of("DiffAdd"), bold = true })
  hl(0, "GitSignsDeleteLnInline", { fg = fg, bg = bg_of("DiffDelete"), bold = true })
end

local function luminance(c)
  local l = {}
  for i = 2, 6, 2 do
    local v = tonumber(c:sub(i, i + 1), 16) / 255
    l[#l + 1] = v <= 0.03928 and v / 12.92 or ((v + 0.055) / 1.055) ^ 2.4
  end
  return 0.2126 * l[1] + 0.7152 * l[2] + 0.0722 * l[3]
end

local function contrast(a, b)
  local la, lb = luminance(a), luminance(b)
  return (math.max(la, lb) + 0.05) / (math.min(la, lb) + 0.05)
end

local function set_comment_floor()
  local function get(name, link)
    return vim.api.nvim_get_hl(0, { name = name, link = link })
  end
  local function hex(n)
    return n and string.format("#%06x", n)
  end
  local fg = hex(get("Normal", false).fg)
  local grounds = {}
  for _, name in ipairs({ "Normal", "DiffAdd", "DiffDelete", "DiffChange" }) do
    grounds[#grounds + 1] = hex(get(name, false).bg)
  end
  if not (fg and grounds[1]) then
    return
  end
  local function worst(c)
    local w = math.huge
    for _, g in ipairs(grounds) do
      w = math.min(w, contrast(c, g))
    end
    return w
  end
  local done = {}
  for _, name in ipairs({ "Comment", "@comment", "@comment.documentation", "SpecialComment" }) do
    local spec = get(name, true)
    while spec.link and spec.link:lower():find("comment") do
      name, spec = spec.link, get(spec.link, true)
    end
    local c = hex(spec.fg)
    if c and not spec.link and not done[name] then
      done[name] = true
      local t = 0
      while t < 1 and worst(blend(fg, c, t)) < 4.5 do
        t = t + 0.01
      end
      spec.fg = blend(fg, c, math.min(t, 1))
      vim.api.nvim_set_hl(0, name, spec)
    end
  end
end

-- nvim-orgmode agenda readability (prefix n a / n t popups). The plugin
-- samples its @org.agenda.* colors from whatever the active theme defines,
-- which under minimal, low-colour families lands scheduled-item text
-- near-invisible. Pin them to semantic groups every family paints; the
-- plugin's own versions are `hi default`, so these explicit links win
-- regardless of load order.
local function set_org_agenda()
  local links = {
    ["@org.agenda.scheduled"] = "Normal",
    ["@org.agenda.scheduled_past"] = "WarningMsg",
    ["@org.agenda.deadline.upcoming"] = "WarningMsg",
    ["@org.agenda.deadline"] = "ErrorMsg",
  }
  for group, target in pairs(links) do
    vim.api.nvim_set_hl(0, group, { link = target })
  end
end

-- Runs on every ColorScheme. A manual :colorscheme (theme audition) won't
-- match the active family's scheme — skip its accents and apply only
-- the theme-agnostic word-diff glue, so auditions aren't painted over.
local function apply_overrides()
  local family, mode = M.read_state()
  local fam = FAMILIES[family]
  -- colors_name: guard override for a family whose light/dark variants both
  -- register ONE shared colors_name (!= schemes[mode]); set fam.colors_name to
  -- it so this match still fires.
  if vim.g.colors_name == (fam.colors_name or fam.schemes[mode]) then
    set_headings(fam.accents[mode])
  end
  set_word_diff()
  set_comment_floor()
  set_org_agenda()
  set_prose()
end

-- Apply family+mode by setting background and re-running :colorscheme. Skips
-- the reload if already active (a reload clears user highlights and re-runs
-- the theme build), unless `force` is set (used for the initial apply).
function M.apply(family, mode, force)
  family, mode = normalize_family(family), normalize_mode(mode)
  local key = family .. "/" .. mode
  if not force and key == applied then
    return
  end
  applied = key
  local fam = FAMILIES[family]
  if fam.pre then
    fam.pre(mode) -- variant globals the theme reads at :colorscheme time
  end
  vim.o.background = mode
  vim.cmd.colorscheme(fam.schemes[mode])
end

function M.apply_from_file(force)
  local family, mode = M.read_state()
  M.apply(family, mode, force)
end

local polls = {} -- libuv fs_poll handles, created lazily in start()

-- Apply the current state now and start watching both state files.
function M.start()
  -- Ensure the state files exist so fs_poll has targets.
  local defaults = { [MODE_FILE] = "dark", [FAMILY_FILE] = DEFAULT_FAMILY }
  for path, value in pairs(defaults) do
    if not vim.uv.fs_stat(path) then
      local f = io.open(path, "w")
      if f then
        f:write(value .. "\n")
        f:close()
      end
    end
  end

  vim.api.nvim_create_autocmd("ColorScheme", {
    group = vim.api.nvim_create_augroup("ThemeOverrides", { clear = true }),
    callback = apply_overrides,
  })

  M.apply_from_file(true)

  if next(polls) then
    return
  end
  for _, path in ipairs({ MODE_FILE, FAMILY_FILE }) do
    local poll = vim.uv.new_fs_poll()
    if poll then
      -- 1s cadence: imperceptible for a manual toggle, negligible overhead.
      poll:start(
        path,
        1000,
        vim.schedule_wrap(function()
          M.apply_from_file(false)
        end)
      )
      polls[#polls + 1] = poll
    end
  end
end

return M
