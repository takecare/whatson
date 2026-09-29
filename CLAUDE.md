# Working on this repo

## Git
- Name each branch after the feature it's about, with a type prefix:
  `feature/barbican-aggregator`, `fix/unionchapel-dates`, `docs/…`, `chore/…`.
  One branch per feature.
- No pull requests: when the work is done and checks pass, merge the branch into
  `main` and push both.

## Checks before merging
- `cd scraper && uv run ruff check . && uv run ruff format --check . && uv run pytest`
- `cd web && npm run typecheck && npm test && npm run build`

See README.md for how the project works and how to add a venue, and PLAN.md for
the roadmap and decisions.
