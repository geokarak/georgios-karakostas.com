# AGENTS.md

## Documentation and plans

- Keep documentation up to date when changes affect it. You can run some quick ripgreps with md files to confirm if needed.
- For docs: Be concise and durable - point to source code for specifics rather than hardcoding values that will get out of sync.
- When finishing work, verify whether related TODO items are now done and should be updated or removed.
- Every time the user starts repeating something very specific about a project, consider adding a rule to this AGENTS.md file.

## Principles

- Every line of code is a liability - we should strive to make our code simple and concise.
- Anytime a new feature is added, unit tests must be written for them.
- I prefer my functions to be small in interface but long in functionality.
- When doing changes, run `make format` and `make check` to confirm all is OK
