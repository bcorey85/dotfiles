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

; Built-in classes read as calls when called; priority beats the LSP class token.
(call
  function: (identifier) @function.call
  (#any-of? @function.call
    "list" "dict" "set" "frozenset" "tuple" "str" "int" "float" "complex" "bool"
    "bytes" "bytearray" "memoryview" "range" "type" "object")
  (#set! priority 130))
