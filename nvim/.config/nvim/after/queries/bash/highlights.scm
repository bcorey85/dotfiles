;; extends

; Top-level variable names at their definition; locals, arguments and uses stay plain.
(program
  (variable_assignment
    name: (variable_name) @declaration.variable
    (#set! priority 130)))

(program
  (declaration_command
    (variable_assignment
      name: (variable_name) @declaration.variable)
    (#set! priority 130)))

(program
  (declaration_command
    (word) @declaration.variable
    (#set! priority 130)))
