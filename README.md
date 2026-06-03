# launchpad-actions

Reusable workflows used by the Launchpad team.

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

**Outputs**

| Name | Description |
|------|-------------|
| `cache_hit` | `true` if the packed charm was served from cache |

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

**Outputs**

| Name | Description |
|------|-------------|
| `charm_revision` | Charm revision number released to Charmhub |
| `resource_revision` | Resource revision number released to Charmhub |

**Secrets required:** `CHARMHUB_TOKEN`

---

### `janitor.yaml` - Clean up old workflow runs

Deletes completed GitHub Actions workflow runs across all workflows in the
calling repository.

**Inputs**

| Name | Required | Default | Description |
|------|----------|---------|-------------|
| `dry_run` | No | `true` | When `true`, log what would be deleted without actually deleting |
| `keep_workflow` | No | - | Filename of a workflow whose runs should never be deleted (e.g. `deploy.yaml`) |

**Permissions required:** `actions: write`, `contents: read`

---

### `refresh-charm-cache.yaml` - Refresh charm cache

Restores the charm build cache in read-only mode to refresh its last-used
timestamp, preventing GitHub's cache eviction policy from expiring it.

**Inputs**

| Name | Required | Default | Description |
|------|----------|---------|-------------|
| `charm_path` | No | `charm` | Path to the charm directory |

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

**Permissions required:** `packages: write`

