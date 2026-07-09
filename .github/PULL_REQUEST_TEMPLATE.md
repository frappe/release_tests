<!-- Thanks for contributing to the Release Manager engine! -->

## What & why


## Type of change
- [ ] New suite / suite extension
- [ ] Bug fix (engine or client)
- [ ] Client / config / CLI change
- [ ] Docs / CI / chore

## Affected suites / apps


## Testing
- [ ] `uv run pytest` passes (mocked, no live site)
- [ ] `uvx ruff check release_tests tests` passes
- [ ] Ran against a live site — versions exercised: <!-- develop / v16 / v15 --> (target/apps: )

## Release-safety checklist
- [ ] Steps are **idempotent** and **non-destructive** on the target site
- [ ] **Version-aware** where behaviour differs (uses `gating`)
- [ ] **Skips cleanly** when `required_app` isn't installed
- [ ] Engine stays **Frappe-free** (no `import frappe`)
- [ ] **No credentials/secrets** committed (`targets.toml` stays gitignored; no `results/`)
