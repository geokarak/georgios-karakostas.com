## Documentation and plans

- If docs were touched, make sure you update them with latest changes. You can run some quick ripgreps with md files to confirm if needed.
- For docs: Be concise and durable - point to source code for specifics rather than hardcoding values that will get out of sync.
- Every time the user starts repeating something very specific about a project, consider adding a rule to this AGENTS.md if this project if one exists.

## Principles

- Every line of code is a liability - we should strive to make our code simple and concise.
- Anytime a new feature is added, unit tests must be written for them 
- I prefer my functions to be small in interface but long in functionality.
- When doing changes, run `make format` and `make check` to confirm all is OK
