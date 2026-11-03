;; extends

; Roles (colors/dredge-roles.lua): names a tag introduces, and filters as calls.
(set_statement
  .
  (expression
    (binary_expression
      (unary_expression
        (primary_expression
          (identifier) @declaration.local))))
  (#set! priority 129))

(for_statement
  (in_expression
    .
    (identifier) @declaration.local)
  (#set! priority 129))

(macro_statement
  (function_call
    .
    (identifier) @declaration.function)
  (#set! priority 129))

(macro_statement
  (function_call
    (arg
      (expression
        (binary_expression
          (unary_expression
            (primary_expression
              (identifier) @declaration.local))))))
  (#set! priority 129))

(binary_expression
  (binary_operator) @_pipe
  .
  (unary_expression
    (primary_expression
      (identifier) @function.call))
  (#eq? @_pipe "|"))
