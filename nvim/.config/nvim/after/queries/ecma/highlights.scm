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

; The LSP sends no token for import names; lowercase named imports are
; almost always functions or hooks.
(import_specifier
  name: (identifier) @function
  (#lua-match? @function "^%l"))

; All-caps globals are builtins, not named constants.
((identifier) @variable.builtin
  (#any-of? @variable.builtin "JSON" "Intl" "Reflect" "Atomics" "globalThis"))
