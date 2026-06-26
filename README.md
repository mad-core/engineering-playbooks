# engineering-playbooks

Catalog of cross-cutting **engineering playbooks** for the `mad-core`
organization. Each playbook is a documented process packaged as a plugin for
Claude Code (and Cowork), discoverable through the marketplace defined in
[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json).

## Playbooks

| Playbook | Purpose |
|---|---|
| [`living-docs`](playbooks/living-docs) | Living-documentation phase — the deterministic docs engine (`gen_docs`) plus the `generate-docs` skill that fills and keeps a repo's structured `/docs` tree alive against the code. |

## Consuming `living-docs`

### As a Claude Code plugin

Add the marketplace and enable the plugin in a consumer repo's
`.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "mad-core": {
      "source": {
        "source": "github",
        "repo": "mad-core/engineering-playbooks"
      }
    }
  },
  "enabledPlugins": {
    "living-docs@mad-core": true
  }
}
```

### As the docs engine (CI / pip)

The deterministic `gen_docs` package is installable directly from this repo:

```bash
pip install "git+https://github.com/mad-core/engineering-playbooks.git#subdirectory=playbooks/living-docs/package"
```

This is what the shared reusable workflows in
[`mad-core/.github`](https://github.com/mad-core/.github)
(`docs-validate` / `docs-sync`) install to run the docs quality gate and the
`/raw` mirror sync.
