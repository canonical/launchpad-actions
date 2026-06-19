# Development

## Setup

On Ubuntu:

```sh
sudo snap install --classic just
sudo snap install --classic astral-uv
uv tool install prek
prek install
```

[`just`](https://github.com/casey/just) runs project tasks,
[`uv`](https://docs.astral.sh/uv/) drives the `terraform-bump-pr`
action, and [`prek`](https://github.com/j178/prek) installs the
pre-commit hooks.

`prek` runs zizmor on every commit; the `prek.yaml` workflow runs the
same check in CI. Run on demand with `prek run --all-files`.

## Tasks

```sh
just          # list recipes
just test     # run terraform-bump-pr unit tests
```

To add a Python dependency to the `terraform-bump-pr` action, run
`uv add <package>` from `actions/terraform-bump-pr/` and commit both
`pyproject.toml` and `uv.lock` (CI runs with `--locked`).

## Workflows

Pin third-party actions to a commit SHA with a `# vX.Y.Z` trailing
comment — zizmor enforces this. Consumers pin this repo by SHA
(`uses: …@<sha>`); merge to `main` and callers bump their SHA.
