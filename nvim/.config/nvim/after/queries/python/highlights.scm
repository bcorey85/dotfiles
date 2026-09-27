;; extends

; Keyword-argument names at a call site name a key, not a traced parameter.
(keyword_argument
  name: (identifier) @variable.member.key)

; Class attributes at their definition, the same colour as their accesses.
(class_definition
  body: (block
    (expression_statement
      (assignment
        left: (identifier) @variable.member
        (#not-lua-match? @variable.member "^_*%u[%u%d_]+$")))))
