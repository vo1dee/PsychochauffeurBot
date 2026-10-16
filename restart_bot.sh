#!/usr/bin/env bash
# Restart the PsychoChauffeur bot on the OCI host (Docker Compose deployment).
#
# Recreates the bot container so changes to .env are picked up, keeping the
# image tag that scripts/deploy_oci.sh last deployed successfully.
# Run from the deployment directory (default: ~/psychochauffeurbot).
set -euo pipefail

cd "$(dirname "$0")"
COMPOSE=(docker compose -f docker-compose.prod.yml)

IMAGE_TAG="${IMAGE_TAG:-$(cat .last_good_tag 2>/dev/null || echo latest)}"
export IMAGE_TAG

echo "Recreating bot container (IMAGE_TAG=$IMAGE_TAG)..."
"${COMPOSE[@]}" up -d --force-recreate --no-deps bot

echo "Checking container status..."
"${COMPOSE[@]}" ps bot

echo "Recent logs:"
"${COMPOSE[@]}" logs --tail=20 bot

echo "Done!"
