;; extends

; Variable names at their definition; arguments and uses stay plain.
(variable_assignment
  name: (variable_name) @declaration.variable
  (#set! priority 130))

(declaration_command
  (word) @declaration.variable
  (#set! priority 130))
