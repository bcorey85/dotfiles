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

; Variable names at their definition; uses stay plain. Priority beats the LSP variable token.
(assignment
  left: (identifier) @declaration.variable
  (#set! priority 130))

(assignment
  left: (pattern_list
    (identifier) @declaration.variable)
  (#set! priority 130))

(for_statement
  left: (identifier) @declaration.variable
  (#set! priority 130))

(for_statement
  left: (pattern_list
    (identifier) @declaration.variable)
  (#set! priority 130))

; Class attributes at their definition.
(class_definition
  body: (block
    (expression_statement
      (assignment
        left: (identifier) @variable.member.attr
        (#not-lua-match? @variable.member.attr "^_*%u[%u%d_]+$")
        (#set! priority 131)))))

; Built-in classes read as calls when called; priority beats the LSP class token.
(call
  function: (identifier) @function.call
  (#any-of? @function.call
    "list" "dict" "set" "frozenset" "tuple" "str" "int" "float" "complex" "bool"
    "bytes" "bytearray" "memoryview" "range" "type" "object")
  (#set! priority 130))
