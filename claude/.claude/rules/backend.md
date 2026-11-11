---
paths:
  - "**/*.py"
  - "**/backend/**"
  - "**/server/**"
  - "**/api/**"
---

# Backend

- Validate every field a new request handler reads at the boundary, before it reaches any service, and reject a bad one with a 400 that names the field.
- Raise or throw the repo's own error class with its error code; never a built-in one such as Error or ValueError.
- Sort every list a new endpoint or query returns by an explicit key.
