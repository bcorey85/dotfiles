;; extends

; Object-literal keys at their definition, apart from member access.
(pair
  key: (property_identifier) @variable.member.key)

(object
  (shorthand_property_identifier) @variable.member.key)

; Keep method-valued keys as methods; the last matching pattern wins.
(pair
  key: (property_identifier) @function.method
  value: [(function_expression) (arrow_function)])

; Function, class and method names at their definition.
(function_declaration
  name: (_) @declaration.function
  (#set! priority 130))

(generator_function_declaration
  name: (_) @declaration.function
  (#set! priority 130))

(method_definition
  name: (_) @declaration.function
  (#set! priority 130))

(class_declaration
  name: (_) @declaration)

; All-caps globals are builtins, not named constants.
((identifier) @variable.builtin
  (#any-of? @variable.builtin "JSON" "Intl" "Reflect" "Atomics" "globalThis"))
