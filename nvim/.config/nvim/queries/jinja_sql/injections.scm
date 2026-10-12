; inherits: jinja

; Layering is Jinja outside, SQL inside (as dbt does): Cube renders Jinja before the
; SQL is parsed, and the SQL grammar cannot parse `{{ ... }}` (it wraps the tag in
; an ERROR node and reads the `safe` filter as the BigQuery SAFE keyword).
; The jinja parser keeps the text between tags as `(content)`; SQL goes there.
; `injection.combined` makes the pieces on either side of a tag one SQL document, so
; `NOT (a AND {{ f() }})` still parses as a whole.
; This lives under its own alias, not plain `jinja`, so description prose that
; shares the jinja parser is never parsed as SQL.
((content) @injection.content
  (#set! injection.language "sql")
  (#set! injection.combined))
