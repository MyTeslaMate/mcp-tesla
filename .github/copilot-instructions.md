# Code Review Guidance for GitHub Copilot

## Review Objectives
- Provide a concise summary of the proposed changes in everyday language.
- Identify potential bugs, regressions, or security concerns introduced by the pull request.
- Check for missing tests or documentation that would help maintain long-term quality.

## Review Process
1. Inspect the diff to understand the intent of the change and its impact on surrounding code.
2. Verify that naming, formatting, and style remain consistent with the existing project conventions.
3. Confirm that any new configuration, dependency, or migration steps are clearly documented.
4. Ensure that test commands listed by the author align with the modified areas and point out gaps when needed.

## Tone and Delivery
- Keep feedback constructive and actionable.
- Prioritize the most critical issues first, then include optional improvements.
- Acknowledge well-executed aspects of the change when appropriate.
