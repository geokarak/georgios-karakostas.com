# AGENTS.md

## Documentation and plans

- Keep documentation up to date when changes affect it. Quick ripgreps in md files can confirm coverage.
- For documentation: Be concise and durable - point to source code for specifics rather than hardcoding values that will get out of sync.
- For documentation: Use generic wording and avoid second-person phrasing such as "you", "your", or variants.
- When finishing work, verify whether related TODO items are now done and should be updated or removed.
- When refactoring Python script entrypoints to import repo-local packages, verify the real invocation style still works (for example `python -m tooling.name` vs `python path/to/name.py`) and update workflows/docs/Make targets to match.
- Every time the user starts repeating something very specific about a project, consider adding a rule to this AGENTS.md file.
- For documentation updates, do not describe how things used to be. Report only the current state and current changes.

## Principles

- Every line of code is a liability - we should strive to make our code simple and concise.
- Anytime a new feature is added, unit tests must be written for them.
- I prefer my functions to be small in interface but long in functionality.
- When doing changes, run `make format` and `make check` to confirm all is OK
