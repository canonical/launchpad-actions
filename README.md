# Launchpad Actions

Reusable workflows used by the Launchpad team.

Call them from a workflow in your repository with `uses:`, pinned to a commit
SHA (shown as `@<ref>` below).

## Workflows

### `build-charm.yaml` - Build charm

Packs a Juju charm with [charmcraft](https://juju.is/docs/sdk/charmcraft),
using `actions/cache` to skip rebuilds when the charm source hasn't changed.

**Inputs**

| Name | Required | Default | Description |
|------|----------|---------|-------------|
| `commit_sha` | No | `github.sha` | Commit SHA to check out |
| `charm_path` | No | `charm` | Path to the charm directory |
| `charmcraft_channel` | No | `3.x/stable` | Charmcraft snap channel to install |
| `runner_arch` | No | `amd64` | Runner architecture: `amd64`, `arm64`, `ppc64el`, `s390x` |
| `runner_base` | No | `noble` | Runner base image: `focal`, `jammy`, `noble` |
| `runner_flavor` | No | `large` | Runner flavor: `small`, `medium`, `large`, `large-extra`, `xlarge`, `xlarge-extra` |

**Outputs**

| Name | Description |
|------|-------------|
| `cache_hit` | `true` if the packed charm was served from cache |

**Usage**

```yaml
jobs:
  charm:
    uses: canonical/launchpad-actions/.github/workflows/build-charm.yaml@<ref>
    secrets: inherit
    with:
      commit_sha: ${{ github.sha }}
      charm_path: "."
```

---

### `release-charm.yaml` - Release charm and OCI resource to Charmhub

Uploads the packed charm and an OCI image resource to Charmhub, then releases
them together on the specified channel.

**Inputs**

| Name | Required | Default | Description |
|------|----------|---------|-------------|
| `charm_cache_hit` | Yes | - | Pass the `cache_hit` output from the `charm` workflow |
| `commit_sha` | Yes | - | Commit SHA used to locate the GHCR image |
| `channel` | Yes | - | Charmhub channel to release to (e.g. `latest/edge`) |
| `charm_name` | Yes | - | Name of the charm on Charmhub |
| `resource_name` | Yes | - | Name of the OCI image resource on Charmhub |
| `charmcraft_channel` | No | `3.x/stable` | Charmcraft snap channel to install |
| `runner_arch` | No | `amd64` | Runner architecture: `amd64`, `arm64`, `ppc64el`, `s390x` |
| `runner_base` | No | `noble` | Runner base image: `focal`, `jammy`, `noble` |
| `runner_flavor` | No | `large` | Runner flavor: `small`, `medium`, `large`, `large-extra`, `xlarge`, `xlarge-extra` |

**Outputs**

| Name | Description |
|------|-------------|
| `charm_revision` | Charm revision number released to Charmhub |
| `resource_revision` | Resource revision number released to Charmhub |

**Secrets required:** `CHARMHUB_TOKEN` — pass `secrets: inherit` from the
calling job.

**Usage**

```yaml
jobs:
  release:
    needs: [oci-image, charm]
    uses: canonical/launchpad-actions/.github/workflows/release-charm.yaml@<ref>
    secrets: inherit
    with:
      charm_cache_hit: ${{ needs.charm.outputs.cache_hit }}
      commit_sha: ${{ inputs.upstream_sha }}
      channel: ${{ inputs.channel }}
      charm_name: forgejo-k8s
      resource_name: forgejo-image
```

---

### `janitor.yaml` - Clean up old workflow runs

Deletes completed GitHub Actions workflow runs across all workflows in the
calling repository.

**Inputs**

| Name | Required | Default | Description |
|------|----------|---------|-------------|
| `dry_run` | No | `true` | When `true`, log what would be deleted without actually deleting |
| `keep_workflows` | No | - | Comma-separated list of workflow filenames whose runs should never be deleted (e.g. `pipeline.yaml,prek.yaml`) |

**Permissions required:** `actions: write`, `contents: read`

**Usage**

```yaml
on:
  schedule:
    - cron: '0 0 * * *' # Daily at midnight UTC
  workflow_dispatch:

permissions:
  actions: write
  contents: read

jobs:
  cleanup:
    uses: canonical/launchpad-actions/.github/workflows/janitor.yaml@<ref>
    with:
      dry_run: false
      keep_workflows: "pipeline.yaml,prek.yaml"
```

---

### `refresh-charm-cache.yaml` - Refresh charm cache

Restores the charm build cache in read-only mode to refresh its last-used
timestamp, preventing GitHub's cache eviction policy from expiring it.

**Inputs**

| Name | Required | Default | Description |
|------|----------|---------|-------------|
| `charm_path` | No | `charm` | Path to the charm directory |

**Usage**

```yaml
on:
  schedule:
    - cron: '0 0 */6 * *' # Every ~6 days at 00:00 UTC

jobs:
  refresh:
    uses: canonical/launchpad-actions/.github/workflows/refresh-charm-cache.yaml@<ref>
    with:
      charm_path: "."
```

---

### `oci-image.yaml` - Build and push OCI image

Clones an upstream repository, builds a Docker image from it, and pushes it
to `ghcr.io/<calling-repo>:<commit_sha>`.

**Inputs**

| Name | Required | Description |
|------|----------|-------------|
| `repo_url` | Yes | Repository URL to clone and build |
| `repo_branch` | Yes | Branch to check out from the upstream repo |
| `commit_sha` | Yes | Commit SHA used as the image tag |
| `runner_arch` | No | Runner architecture: `amd64` (default), `arm64`, `ppc64el`, `s390x` |
| `runner_base` | No | Runner base image: `focal`, `jammy`, `noble` (default) |
| `runner_flavor` | No | Runner flavor: `small`, `medium`, `large` (default), `large-extra`, `xlarge`, `xlarge-extra` |

**Permissions required:** `packages: write`

**Usage**

```yaml
jobs:
  oci-image:
    permissions:
      contents: read
      packages: write
    uses: canonical/launchpad-actions/.github/workflows/oci-image.yaml@<ref>
    with:
      repo_url: https://codeberg.org/forgejo/forgejo.git
      repo_branch: forgejo
      commit_sha: ${{ inputs.upstream_sha }}
```

---

### `prek.yaml` - Run prek (pre-commit) checks

Runs [prek](https://github.com/j178/prek) pre-commit hooks on the calling
repository. Takes no inputs.

**Permissions required:** `contents: read`

**Usage**

```yaml
on:
  pull_request:
    branches:
      - main
  push:
    branches:
      - main
  workflow_call:
  schedule:
    - cron: "0 0 * * *" # Daily at midnight UTC

permissions: read-all

jobs:
  prek:
    uses: canonical/launchpad-actions/.github/workflows/prek.yaml@<ref>
```

---

### `sync.yaml` - Mirror a repository and trigger a downstream workflow

Mirrors all refs from a source repository to the calling GitHub repository.
Sync occurs whenever any ref differs between the two. Downstream triggering is
gated independently on a specific named ref.

**Behavior**

- Compares the complete ref listing (`git ls-remote`) between source and the
calling repository. Mirrors via `git push --mirror --force` whenever any ref
differs.
- If `trigger_workflow` is set, the downstream workflow is triggered **only**
when the named `trigger_ref` changed — not when unrelated refs (tags, other
branches) were updated. This avoids firing downstream pipelines
unnecessarily while still pushing all changes.

**Inputs**

| Name | Required | Default | Description |
|------|----------|---------|-------------|
| `source_url` | Yes | - | Git URL of the source repository to mirror from |
| `trigger_workflow` | No | - | Downstream workflow file to trigger after a successful sync |
| `trigger_ref` | No | `main` | Ref whose change gates downstream triggering |
| `trigger_inputs_json` | No | `{}` | JSON string of extra inputs for the triggered workflow |

**Outputs**

| Name | Description |
|------|-------------|
| `changed` | `true` if any ref differed between source and target |

**Permissions required:** `contents: write`, `actions: write`

**Usage**

```yaml
on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:

permissions:
  contents: write
  actions: write

jobs:
  sync:
    uses: canonical/launchpad-actions/.github/workflows/sync.yaml@<ref>
    with:
      source_url: https://codeberg.org/forgejo/forgejo.git
      trigger_workflow: pipeline.yaml
      trigger_ref: main
```
