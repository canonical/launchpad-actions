#!/usr/bin/env bash
# Commit the bumped Terraform file. Two modes:
#   MODE=pr       - push to a unique branch, open a PR, close older bump PRs.
#   MODE=direct   - commit straight to TF_BASE_BRANCH and push.
#
# Expects the Terraform checkout at ./terraform-repo and the following
# environment variables:
#   GH_TOKEN, TF_REPO, APP_NAME, CHARM_REVISION, RESOURCE_REVISION,
#   TF_FILE_PATH, TF_BASE_BRANCH, MODE
set -euo pipefail
cd terraform-repo

# Checkout ran with persist-credentials: false, so attach the token to the
# remote URL for the upcoming push (no credentials linger in artifacts).
git remote set-url origin "https://x-access-token:${GH_TOKEN}@github.com/${TF_REPO}.git"

if git diff --quiet; then
  echo "No Terraform changes required; skipping."
  exit 0
fi

COMMIT_MSG="chore(${APP_NAME}): bump charm to rev ${CHARM_REVISION}, app-image to rev ${RESOURCE_REVISION}"

case "${MODE}" in
  pr)
    BRANCH="bump-revision-app-${RESOURCE_REVISION}-charm-${CHARM_REVISION}-${GITHUB_RUN_ID}"
    git switch -c "$BRANCH"
    ;;
  direct)
    # Already on TF_BASE_BRANCH from the checkout step; commit lands there.
    ;;
  *)
    echo "Invalid MODE: ${MODE} (expected pr|direct)" >&2
    exit 2
    ;;
esac

git add -- "${TF_FILE_PATH}"
git -c user.name="github-actions[bot]" \
    -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
    commit -m "${COMMIT_MSG}"

if [[ "${MODE}" == "direct" ]]; then
  git push origin "HEAD:${TF_BASE_BRANCH}"
  echo "Pushed bump commit directly to ${TF_BASE_BRANCH}."
  exit 0
fi

git push -u origin HEAD

RUN_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
BODY="$(printf '## Summary\n- Bumps the `%s` charm revision and `app-image` resource revision.\n\n## Source\n- Actions run: %s\n' "${APP_NAME}" "${RUN_URL}")"
gh pr create \
  --base "${TF_BASE_BRANCH}" \
  --title "${COMMIT_MSG}" \
  --body "$BODY"

NEW_PR_NUMBER="$(gh pr view --json number --jq '.number')"
echo "Created PR #${NEW_PR_NUMBER}"

# Close any older open bump PRs so only the latest remains.
mapfile -t OLD_PRS < <(
  gh pr list --state open --json number,headRefName,title --jq '
    map(
      select(
        (.headRefName | startswith("bump-revision-app-"))
        and (.title | contains("): bump charm to rev "))
      )
    )
    | .[].number
  '
)

for pr in "${OLD_PRS[@]}"; do
  if [[ "${pr}" == "${NEW_PR_NUMBER}" ]]; then
    continue
  fi
  echo "Closing superseded PR #${pr}"
  gh pr close "${pr}" \
    --comment "Superseded by #${NEW_PR_NUMBER}." \
    --delete-branch || true
done
