# `workflow-templates/` — GitHub Actions caller templates

These are the two **thin caller** workflows `/init-docs` drops into a target
repo's `.github/workflows/`. Each only calls an org-wide *reusable* workflow
maintained centrally in `mad-core/.github` (the shared docs CI/CD) — the target repo carries no docs logic of its own, just the wiring.

| Template | Trigger | Calls | Purpose |
|---|---|---|---|
| [`docs-validate.yml`](docs-validate.yml) | `pull_request` | `docs-validate.reusable.yml@main` | gate PRs on docs being in sync |
| [`docs-sync.yml`](docs-sync.yml) | `push` to `develop` | `docs-sync.reusable.yml@main` | regenerate/update docs after merge |

## The doubled `.github/.github/` path is correct

```yaml
uses: mad-core/.github/.github/workflows/docs-validate.reusable.yml@main
#               └ repo ┘ └────── path inside that repo ──────┘
```

The org's shared workflows live in a repo literally named `.github`, and a repo
stores its workflows under `.github/workflows/`. So the reference is
`<org>/.github` (the repo) + `/.github/workflows/<file>` (the path) — the
repetition is the repo name meeting its own workflows directory, not a typo.

## Configuration

Both templates read `service_slug` from the `SERVICE_SLUG` **repo variable**
(`${{ vars.SERVICE_SLUG }}`) and pass org secrets through with `secrets:
inherit` — so the dropped files are identical across repos and need no edit
beyond the `branches:` list. `/init-docs` prints the secrets/vars checklist
(set `SERVICE_SLUG`, `DOCS_SYNC_TOKEN`, `ANTHROPIC_API_KEY`) at the end of its
run.
