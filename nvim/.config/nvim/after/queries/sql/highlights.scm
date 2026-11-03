;; extends

; Roles (colors/dredge-roles.lua): names a statement introduces, and tables or columns it writes.
(cte
  .
  (identifier) @declaration.local
  (#set! priority 129))

(relation
  alias: (identifier) @declaration.local
  (#set! priority 129))

(term
  alias: (identifier) @declaration.local
  (#set! priority 129))

(create_table
  (object_reference
    name: (identifier) @declaration.local)
  (#set! priority 129))

(column_definition
  name: (identifier) @declaration.local
  (#set! priority 129))

(insert
  (object_reference
    name: (identifier) @variable.write)
  (#set! priority 131))

(update
  (relation
    (object_reference
      name: (identifier) @variable.write))
  (#set! priority 131))

(assignment
  left: (field
    name: (identifier) @variable.write)
  (#set! priority 131))
