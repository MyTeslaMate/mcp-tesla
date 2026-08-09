# Instructions for Contributors

These guidelines define how agents should work within this repository.

## Coding Standards
- Write Python following [PEP 8](https://peps.python.org/pep-0008/) style conventions unless a file documents stricter rules.
- Prefer descriptive function and variable names; avoid abbreviations unless they are domain specific and well known.
- Keep functions small and focused. Extract helpers when logic becomes complex or reused.
- Add or update docstrings for public modules, classes, and functions to explain their roles and important parameters.

## Testing Expectations
- Run the relevant unit or integration test targets for any area you modify.
- Document the exact commands executed in the testing section of the pull request description.
- If a change cannot be tested automatically, explain why and detail any manual verification performed.

## Communication
- Keep commit messages and pull request descriptions concise but informative.
- Highlight any follow-up work or known limitations discovered during development.
- When touching configuration or tooling, mention potential impacts on local development or CI pipelines.
