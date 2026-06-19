#!/usr/bin/env bash
# Validate the user-supplied inputs before they reach a branch name, commit
# message, PR title or a juju resource selector.
# Expects the following environment variables:
#   APP_NAME, CHARM_REVISION, RESOURCE_REVISION, TF_FILE_PATH, TF_BASE_BRANCH,
#   MODE
set -euo pipefail

# Reject anything that isn't a plain integer before it reaches a branch name,
# commit message or PR title.
if ! [[ "${CHARM_REVISION}" =~ ^[0-9]+$ ]]; then
  echo "charm_revision must be a non-negative integer, got: ${CHARM_REVISION}" >&2
  exit 2
fi
if ! [[ "${RESOURCE_REVISION}" =~ ^[0-9]+$ ]]; then
  echo "resource_revision must be a non-negative integer, got: ${RESOURCE_REVISION}" >&2
  exit 2
fi
# Constrain the file path: relative, no traversal, no shell/glob metacharacters.
if [[ "${TF_FILE_PATH}" == /* || "${TF_FILE_PATH}" == *..* \
      || ! "${TF_FILE_PATH}" =~ ^[A-Za-z0-9._/-]+$ ]]; then
  echo "Invalid tf_file_path: ${TF_FILE_PATH}" >&2
  exit 2
fi
# Branch names must be a simple, git-safe slug.
if ! [[ "${TF_BASE_BRANCH}" =~ ^[A-Za-z0-9._/-]+$ ]]; then
  echo "Invalid tf_base_branch: ${TF_BASE_BRANCH}" >&2
  exit 2
fi
# App name ends up in a juju resource selector and PR text.
if ! [[ "${APP_NAME}" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Invalid app_name: ${APP_NAME}" >&2
  exit 2
fi
# MODE selects between PR and direct-commit flows.
if [[ "${MODE}" != "pr" && "${MODE}" != "direct" ]]; then
  echo "Invalid mode: ${MODE} (expected pr|direct)" >&2
  exit 2
fi
