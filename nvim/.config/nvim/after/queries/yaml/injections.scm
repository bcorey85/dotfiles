; extends

; Cube.dev data models are YAML that embed two other languages, so highlighting
; the YAML alone leaves the parts that matter most unhighlighted:
;   1. `sql:` values are SQL (block scalars and one-line strings), or SQL mixed with
;      Jinja tags (`jinja_sql`, below).
;   2. Cube renders Jinja BEFORE it parses the YAML, so `{{ ... }}` appears inside
;      descriptions, quoted strings, and unquoted as a whole value
;      (`meta: {{ measure_meta('cube.m') | safe }}`, which the YAML grammar reads
;      as a flow mapping nested in a flow mapping).
; `; extends` keeps the bundled yaml injections (comment, bash `run:`, promql `expr:`).
; Inject `jinja`, never `jinja_inline`: jinja_inline parses the whole scalar as one
; expression, so prose lights up keywords mid-word ("Centerb*as*e", "*in*voice").
; The `jinja` parser keeps plain text as content and injects jinja_inline only
; inside the `{{ }}` delimiters.
; The key `sql` is excluded from the Jinja rules below (#not-eq?): a `sql:` value is
; SQL, and when it also contains `{{ ... }}` it is injected as `jinja_sql` instead
; of `sql`. `jinja_sql` is Jinja outside with SQL injected into its plain text
; (queries/jinja_sql/), so the tags are colored like description prose AND the SQL
; around them is still SQL. Plain `sql` cannot parse a tag: it wraps it in an ERROR
; node and leaves its function names, strings and kwargs uncolored.

; --- SQL in `sql:` values (no `{{`) -------------------------------------------

; Block scalar (`sql: |` / `sql: >`). The offset skips the `|` / `>` header line.
(block_mapping_pair
  key: (flow_node) @_key
  (#eq? @_key "sql")
  value: (block_node
    (block_scalar) @injection.content
    (#not-match? @injection.content "\\{\\{")
    (#set! injection.language "sql")
    (#offset! @injection.content 0 1 0 0)))

; Unquoted one-line value.
(block_mapping_pair
  key: (flow_node) @_key
  (#eq? @_key "sql")
  value: (flow_node
    (plain_scalar
      (string_scalar) @injection.content)
    (#not-match? @injection.content "\\{\\{")
    (#set! injection.language "sql")))

; Quoted values. The offset drops the surrounding quote characters.
(block_mapping_pair
  key: (flow_node) @_key
  (#eq? @_key "sql")
  value: (flow_node
    (double_quote_scalar) @injection.content
    (#not-match? @injection.content "\\{\\{")
    (#set! injection.language "sql")
    (#offset! @injection.content 0 1 0 -1)))

(block_mapping_pair
  key: (flow_node) @_key
  (#eq? @_key "sql")
  value: (flow_node
    (single_quote_scalar) @injection.content
    (#not-match? @injection.content "\\{\\{")
    (#set! injection.language "sql")
    (#offset! @injection.content 0 1 0 -1)))

; --- SQL mixed with Jinja in `sql:` values (`{{`) -----------------------------

(block_mapping_pair
  key: (flow_node) @_key
  (#eq? @_key "sql")
  value: (block_node
    (block_scalar) @injection.content
    (#match? @injection.content "\\{\\{")
    (#set! injection.language "jinja_sql")
    (#offset! @injection.content 0 1 0 0)))

(block_mapping_pair
  key: (flow_node) @_key
  (#eq? @_key "sql")
  value: (flow_node
    (plain_scalar
      (string_scalar) @injection.content)
    (#match? @injection.content "\\{\\{")
    (#set! injection.language "jinja_sql")))

(block_mapping_pair
  key: (flow_node) @_key
  (#eq? @_key "sql")
  value: (flow_node
    (double_quote_scalar) @injection.content
    (#match? @injection.content "\\{\\{")
    (#set! injection.language "jinja_sql")
    (#offset! @injection.content 0 1 0 -1)))

(block_mapping_pair
  key: (flow_node) @_key
  (#eq? @_key "sql")
  value: (flow_node
    (single_quote_scalar) @injection.content
    (#match? @injection.content "\\{\\{")
    (#set! injection.language "jinja_sql")
    (#offset! @injection.content 0 1 0 -1)))

; --- Jinja in every other scalar that contains `{{` ---------------------------

; Block scalar (description / ai_context prose).
(block_mapping_pair
  key: (flow_node) @_key
  (#not-eq? @_key "sql")
  value: (block_node
    (block_scalar) @injection.content
    (#match? @injection.content "\\{\\{")
    (#set! injection.language "jinja")
    (#offset! @injection.content 0 1 0 0)))

; Unquoted one-line value.
(block_mapping_pair
  key: (flow_node) @_key
  (#not-eq? @_key "sql")
  value: (flow_node
    (plain_scalar
      (string_scalar) @injection.content)
    (#match? @injection.content "\\{\\{")
    (#set! injection.language "jinja")))

; Quoted values.
(block_mapping_pair
  key: (flow_node) @_key
  (#not-eq? @_key "sql")
  value: (flow_node
    (double_quote_scalar) @injection.content
    (#match? @injection.content "\\{\\{")
    (#set! injection.language "jinja")
    (#offset! @injection.content 0 1 0 -1)))

(block_mapping_pair
  key: (flow_node) @_key
  (#not-eq? @_key "sql")
  value: (flow_node
    (single_quote_scalar) @injection.content
    (#match? @injection.content "\\{\\{")
    (#set! injection.language "jinja")
    (#offset! @injection.content 0 1 0 -1)))

; Unquoted `{{ ... }}` as a whole value: the outer flow_mapping's text starts with
; `{{` (the inner one starts with `{ `, so it does not match and is not injected twice).
(block_mapping_pair
  key: (flow_node) @_key
  (#not-eq? @_key "sql")
  value: (flow_node
    (flow_mapping) @injection.content
    (#match? @injection.content "^\\{\\{")
    (#set! injection.language "jinja")))
