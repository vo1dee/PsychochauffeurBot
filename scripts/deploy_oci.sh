#!/usr/bin/env bash
# Deploy a bot image tag on the OCI host and roll back if it does not stay up.
#
# Invoked by .github/workflows/deploy.yml over SSH (piped via `bash -s`), or
# manually on the host:  IMAGE_TAG=sha-abc1234 ./scripts/deploy_oci.sh
#
# Env:
#   IMAGE_TAG       tag to deploy (required)
#   APP_DIR         deployment directory (default: ~/psychochauffeurbot)
#   GHCR_USER/GHCR_TOKEN  optional short-lived registry login for private images
#   STABLE_SECONDS  how long the container must stay running (default: 60)
set -euo pipefail

: "${IMAGE_TAG:?IMAGE_TAG is required}"
APP_DIR="${APP_DIR:-$HOME/psychochauffeurbot}"
STABLE_SECONDS="${STABLE_SECONDS:-60}"
COMPOSE=(docker compose -f docker-compose.prod.yml)

cd "$APP_DIR"
[[ -f .env ]] || { echo "Missing $APP_DIR/.env" >&2; exit 1; }

if [[ -n "${GHCR_TOKEN:-}" ]]; then
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "${GHCR_USER:-github}" --password-stdin >/dev/null
  trap 'docker logout ghcr.io >/dev/null 2>&1 || true' EXIT
fi

previous_tag="$(cat .last_good_tag 2>/dev/null || true)"

start_tag() {
  echo "==> Starting bot with IMAGE_TAG=$1"
  IMAGE_TAG="$1" "${COMPOSE[@]}" pull bot
  IMAGE_TAG="$1" "${COMPOSE[@]}" up -d --remove-orphans
}

# The bot is a long-polling process with no HTTP endpoint, so "healthy" means the
# container is still running without restarts after STABLE_SECONDS.
is_stable() {
  local container deadline state restarts
  container="$("${COMPOSE[@]}" ps -q bot)"
  [[ -n "$container" ]] || return 1
  deadline=$((SECONDS + STABLE_SECONDS))
  while (( SECONDS < deadline )); do
    state="$(docker inspect -f '{{.State.Status}}' "$container")"
    restarts="$(docker inspect -f '{{.RestartCount}}' "$container")"
    if [[ "$state" != "running" || "$restarts" != "0" ]]; then
      echo "Container state=$state restarts=$restarts" >&2
      return 1
    fi
    sleep 5
  done
}

# Every deploy pulls a ~1.9 GB tag, and `image prune` never removes tagged images,
# so delete every bot tag except the one just deployed and the rollback target.
prune_old_images() {
  local repo="ghcr.io/vo1dee/psychochauffeurbot" tag
  docker images "$repo" --format '{{.Tag}}' | while read -r tag; do
    [[ "$tag" == "$IMAGE_TAG" || "$tag" == "$previous_tag" ]] && continue
    docker rmi "$repo:$tag" >/dev/null 2>&1 || true
  done
  docker image prune -f >/dev/null || true
  docker builder prune -f --filter "until=168h" >/dev/null || true
}

start_tag "$IMAGE_TAG"
if is_stable; then
  echo "$IMAGE_TAG" > .last_good_tag
  echo "==> Deployed $IMAGE_TAG"
  prune_old_images
  exit 0
fi

echo "==> $IMAGE_TAG failed to stay up; recent logs:" >&2
"${COMPOSE[@]}" logs --tail=80 bot >&2 || true
if [[ -n "$previous_tag" && "$previous_tag" != "$IMAGE_TAG" ]]; then
  echo "==> Rolling back to $previous_tag" >&2
  start_tag "$previous_tag"
  is_stable && echo "==> Rollback to $previous_tag succeeded" >&2
fi
exit 1
