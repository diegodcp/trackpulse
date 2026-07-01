# packages/test-fixtures

Fixture package placeholder for deterministic replay assets.

## Generated files policy for agents

**Only commit reviewed golden fixtures. Never commit generated dev or full fixtures.**

| Path pattern | Commit? |
|---|---|
| `examples/fixtures/**/golden/` | Yes — small reviewed snapshots only |
| `examples/fixtures/**/dev/` | **No** — gitignored |
| `examples/fixtures/**/full/` | **No** — gitignored; can be hundreds of MB |
| `examples/fixtures/**/raw/` | **No** — gitignored intermediate download output |
| `examples/fixtures/**/normalized/` | **No** — gitignored intermediate pipeline output |
| `.data/` | **No** — gitignored scratch directory |

Golden fixtures must be small (a handful of sessions, weather, and location records
for a handful of drivers). Run the downloader with `--level golden` to produce them,
review the output, then commit.

If the fixture downloader produces dev or full output, verify it is listed in
`.gitignore` before running `git add`. **Never force-add `raw/`, `normalized/`,
`dev/`, or `full/` directories.**

## Credentials

Do not store OpenF1 credentials in fixture files or test helpers. Fixture mode and
golden fixture replay work without any authentication. See `.env.example` for the
correct placeholder format.
