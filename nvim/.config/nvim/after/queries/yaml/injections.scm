; extends

; Cube.dev data models are YAML with Jinja in them: Cube renders Jinja BEFORE it
; parses the YAML, so `{{ ... }}` appears inside descriptions, quoted strings,
; `sql:` values, and unquoted as a whole value
; (`meta: {{ measure_meta('cube.m') | safe }}`, which the YAML grammar reads
; as a flow mapping nested in a flow mapping).
; `; extends` keeps the bundled yaml injections (comment, bash `run:`, promql `expr:`).
; Inject `jinja`, never `jinja_inline`: jinja_inline parses the whole scalar as one
; expression, so prose lights up keywords mid-word ("Centerb*as*e", "*in*voice").
; The `jinja` parser keeps plain text as content and injects jinja_inline only
; inside the `{{ }}` delimiters.
; `sql:` values are deliberately NOT injected as `sql`. They are expression
; fragments with `{CUBE}` / `{member}` placeholders, not statements, so the sql
; grammar error-recovers and drops keywords (`NOT ({CUBE}.x IS NOT NULL AND )`
; loses the leading NOT) and keywords color inconsistently. SQL words in `sql:`
; values are colored by lua/config/cube_sql.lua instead. A `sql:` value that
; contains `{{` still gets the `jinja` injection below, so its tags color like
; the ones in descriptions.

; --- Jinja in every scalar that contains `{{` ----------------------------------

; Block scalar (description / ai_context prose, `sql: |`).
(block_mapping_pair
  key: (flow_node)
  value: (block_node
    (block_scalar) @injection.content
    (#match? @injection.content "\\{\\{")
    (#set! injection.language "jinja")
    (#offset! @injection.content 0 1 0 0)))

; Unquoted one-line value.
(block_mapping_pair
  key: (flow_node)
  value: (flow_node
    (plain_scalar
      (string_scalar) @injection.content)
    (#match? @injection.content "\\{\\{")
    (#set! injection.language "jinja")))

; Quoted values.
(block_mapping_pair
  key: (flow_node)
  value: (flow_node
    (double_quote_scalar) @injection.content
    (#match? @injection.content "\\{\\{")
    (#set! injection.language "jinja")
    (#offset! @injection.content 0 1 0 -1)))

(block_mapping_pair
  key: (flow_node)
  value: (flow_node
    (single_quote_scalar) @injection.content
    (#match? @injection.content "\\{\\{")
    (#set! injection.language "jinja")
    (#offset! @injection.content 0 1 0 -1)))

; Unquoted `{{ ... }}` as a whole value: the outer flow_mapping's text starts with
; `{{` (the inner one starts with `{ `, so it does not match and is not injected twice).
(block_mapping_pair
  key: (flow_node)
  value: (flow_node
    (flow_mapping) @injection.content
    (#match? @injection.content "^\\{\\{")
    (#set! injection.language "jinja")))
