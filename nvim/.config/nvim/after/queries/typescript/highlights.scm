;; extends

; null and undefined in a type position, apart from the values.
(literal_type
  [(null) (undefined)] @constant.builtin.type
  (#set! priority 110))
