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
-- headings, gitsigns word-diff, per-family fixups), re-applied on ColorScheme,
-- so a family switch always lands with the right set. Plugin specs stay pure
-- plugin declarations. Keep FAMILIES in sync with theme-mode's registry and
-- the ghostty/herdr theme files.

local M = {}

local MODE_FILE = vim.env.HOME .. "/.cache/theme-mode"
local FAMILY_FILE = vim.env.HOME .. "/.cache/theme-family"
local DEFAULT_FAMILY = "vitesse"

-- alpha-blend two hex colours (a = share of c1).
local function blend(c1, c2, a)
  local out = {}
  for i = 2, 6, 2 do
    local v = tonumber(c1:sub(i, i + 1), 16) * a + tonumber(c2:sub(i, i + 1), 16) * (1 - a)
    out[#out + 1] = string.format("%02x", math.floor(v + 0.5))
  end
  return "#" .. table.concat(out)
end

-- Registry shape: the mode axis, the fixup hook and the state-file plumbing
-- all key off this table — adding a family is an entry here plus theme-mode's
-- cases and the ghostty/herdr files.
local FAMILIES = {
  ["vitesse"] = {
    -- bcorey85/vitesse.nvim: our own port of antfu's Vitesse, DARK + LIGHT. Off-
    -- black #121212 / white #ffffff, desaturated low-halation accents. Single
    -- colorscheme "vitesse" follows vim.o.background, so pin colors_name.
    schemes = { dark = "vitesse", light = "vitesse" },
    colors_name = "vitesse",
    accents = {
      dark = { heading1 = "#d9739f", heading = "#e6cc77" }, -- magenta + yellow
      light = { heading1 = "#a13865", heading = "#bda437" },
    },
    -- antfu's comments read low: #758575 ~3.9:1 on #121212, #a0ada0 ~2.3:1 on
    -- #ffffff. Lift both to clear 4.5:1 (prose readability > authored hue).
    fixup = function(mode)
      local fg = mode == "light" and "#6b7a6b" or "#78877a"
      vim.api.nvim_set_hl(0, "Comment", { fg = fg, italic = true })
    end,
  },
  ["flexoki"] = {
    -- kepano/flexoki-neovim: one colorscheme "flexoki" switches via
    -- vim.o.background (dark #100f0f / light #fffcf0), so both modes share
    -- colors_name and the scheme name is pinned here.
    schemes = { dark = "flexoki", light = "flexoki" },
    colors_name = "flexoki",
    accents = {
      dark = { heading1 = "#8b7ec8", heading = "#4385be" }, -- purple + blue (400)
      light = { heading1 = "#5e409d", heading = "#205ea6" }, -- purple + blue (600)
    },
    -- Comment floor: flexoki's stock comment is deliberately faint and fails the
    -- 4.5:1 floor in both modes (dark base-700 #575653 is ~2.5:1 on #100f0f;
    -- light base-300 #b7b5ac is ~1.9:1 on #fffcf0). Lift to base-500 #878580
    -- dark (~5.3:1) and base-600 #6f6e69 light (~4.9:1). Flexoki comments are not
    -- italic, so this stays flat — nvim_set_hl replaces the whole group.
    fixup = function(mode)
      local fg = mode == "light" and "#6f6e69" or "#878580"
      vim.api.nvim_set_hl(0, "Comment", { fg = fg })
    end,
  },
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
    -- Comment floor: the `Comment` group is light_grey #838781, which misses
    -- 4.5:1 in both modes (~4.2:1 on #252623, ~3.5:1 on #fafae0). Lift to
    -- #8e938c dark (~4.9:1) and #66695f light (~5.3:1). Treesitter's @comment
    -- is a separate, already-legible colour (bg_yellow) and is left alone.
    -- bamboo's comments are italic, so keep the slant (nvim_set_hl replaces
    -- the whole group).
    fixup = function(mode)
      local fg = mode == "light" and "#66695f" or "#8e938c"
      vim.api.nvim_set_hl(0, "Comment", { fg = fg, italic = true })
    end,
  },
  ["gruvbox"] = {
    -- ellisonleao/gruvbox.nvim: ORIGINAL gruvbox, medium contrast. One
    -- colorscheme "gruvbox" follows vim.o.background (dark #282828 / light
    -- cream #fbf1c7) and keeps that one colors_name in both, so it is pinned.
    schemes = { dark = "gruvbox", light = "gruvbox" },
    colors_name = "gruvbox",
    accents = {
      dark = { heading1 = "#fb4934", heading = "#fabd2f" }, -- red + yellow
      light = { heading1 = "#9d0006", heading = "#b57614" },
    },
    -- Comment floor: the stock comment is grey #928374 in BOTH modes, which
    -- misses 4.5:1 at each end (~4.0:1 on #282828, ~3.2:1 on #fbf1c7) — the one
    -- colour has to move in opposite directions. Lift to #9e8d7d dark (~4.6:1)
    -- and darken to #776a5e light (~4.6:1). gruvbox's comments are italic, so
    -- keep the slant (nvim_set_hl replaces the whole group).
    fixup = function(mode)
      local fg = mode == "light" and "#776a5e" or "#9e8d7d"
      vim.api.nvim_set_hl(0, "Comment", { fg = fg, italic = true })
    end,
  },
  ["melange"] = {
    -- savq/melange-nvim: one colorscheme "melange" follows vim.o.background
    -- (warm brown-black #292522 / neutral #f1f1f1), sharing one colors_name.
    schemes = { dark = "melange", light = "melange" },
    colors_name = "melange",
    accents = {
      dark = { heading1 = "#e49b5d", heading = "#ebc06d" }, -- orange + yellow
      light = { heading1 = "#bc5c00", heading = "#a06d00" },
    },
    -- No fixup: melange is the only family whose stock comments already clear
    -- 4.5:1 at both ends (#c1a78e ~6.7:1 on #292522, #7d6658 ~4.8:1 on #f1f1f1).
  },
  ["kanagawa"] = {
    -- rebelot/kanagawa.nvim. Unlike every other family, kanagawa ships one
    -- colorscheme PER variant rather than switching on vim.o.background — so
    -- the schemes differ by mode. Both still register colors_name "kanagawa",
    -- so that is pinned for the override guard.
    schemes = { dark = "kanagawa-dragon", light = "kanagawa-lotus" },
    colors_name = "kanagawa",
    accents = {
      dark = { heading1 = "#a292a3", heading = "#c4b28a" }, -- mauve + yellow
      light = { heading1 = "#b35b79", heading = "#836f4a" },
    },
    -- Comment floor: dragon's #737c73 is ~4.2:1 on #181616 and lotus's #8a8980
    -- is ~2.9:1 on #f2ecbc. Lift to #838a82 (~5.1:1) and #6a6a5e (~4.6:1) — the
    -- same two values the hunk and herdr kanagawa palettes already encode.
    -- Kanagawa's comments are italic, so keep the slant.
    fixup = function(mode)
      local fg = mode == "light" and "#6a6a5e" or "#838a82"
      vim.api.nvim_set_hl(0, "Comment", { fg = fg, italic = true })
    end,
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
-- match the active family's scheme — skip its fixup/accents and apply only
-- the theme-agnostic word-diff glue, so auditions aren't painted over.
local function apply_overrides()
  local family, mode = M.read_state()
  local fam = FAMILIES[family]
  -- colors_name: guard override for a family whose light/dark variants both
  -- register ONE shared colors_name (!= schemes[mode]); set fam.colors_name to
  -- it so this match still fires.
  if vim.g.colors_name == (fam.colors_name or fam.schemes[mode]) then
    if fam.fixup then
      fam.fixup(mode) -- before word-diff: it reads the Diff* bgs set here
    end
    set_headings(fam.accents[mode])
  end
  set_word_diff()
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
