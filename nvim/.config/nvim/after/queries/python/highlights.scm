;; extends

; Keyword-argument names at a call site.
(keyword_argument
  name: (identifier) @variable.kwarg)

; Function and class names at their definition.
(function_definition
  name: (identifier) @declaration.function
  (#set! priority 130))

(class_definition
  name: (identifier) @declaration.class
  (#set! priority 130))

; Module-level variable names at their definition; locals and uses stay plain.
(module
  (expression_statement
    (assignment
      left: (identifier) @declaration.variable
      (#set! priority 130))))

(module
  (expression_statement
    (assignment
      left: (pattern_list
        (identifier) @declaration.variable)
      (#set! priority 130))))

; Class attributes at their definition.
(class_definition
  body: (block
    (expression_statement
      (assignment
        left: (identifier) @variable.member.attr
        (#not-lua-match? @variable.member.attr "^_*%u[%u%d_]+$")
        (#set! priority 131)))))

; Roles (colors/dredge-roles.lua): local binds, writes and exits. dredge leaves these plain.
(assignment
  left: (identifier) @declaration.local
  (#set! priority 129))

(for_statement
  left: (identifier) @declaration.local
  (#set! priority 129))

(for_in_clause
  left: (identifier) @declaration.local
  (#set! priority 129))

; The written name only: the attribute, or the container of a subscript; keys keep their own role.
(assignment
  left: (attribute
    attribute: (identifier) @variable.write)
  (#set! priority 131))

(augmented_assignment
  left: (attribute
    attribute: (identifier) @variable.write)
  (#set! priority 131))

(assignment
  left: (subscript
    value: (_) @variable.write)
  (#set! priority 131))

(augmented_assignment
  left: (subscript
    value: (_) @variable.write)
  (#set! priority 131))

(augmented_assignment
  left: (identifier) @variable.write
  (#set! priority 131))

(raise_statement
  "raise" @keyword.exit)

(break_statement) @keyword.exit

(continue_statement) @keyword.exit

; Built-in classes read as calls when called; priority beats the LSP class token.
(call
  function: (identifier) @function.call
  (#any-of? @function.call
    "list" "dict" "set" "frozenset" "tuple" "str" "int" "float" "complex" "bool"
    "bytes" "bytearray" "memoryview" "range" "type" "object")
  (#set! priority 130))
