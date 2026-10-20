#!/usr/bin/env bash
# ==============================================================================
# Unified Deployment & CI Runner via Google Cloud Build
# Usage:
#   ./deployment/deploy.sh dev          # Bootstrap & deploy to dev (travel-agent-511710)
#   ./deployment/deploy.sh staging      # Bootstrap & deploy to staging (travel-agent-staging-51221)
#   ./deployment/deploy.sh prod         # Bootstrap & deploy to prod (travel-agent-prod-512211)
#   ./deployment/deploy.sh pr-check dev # Run CI PR checks (unit tests, frontend build, tf validate)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REGION="${REGION:-europe-west9}"

get_project_id() {
  case "$1" in
    dev)     echo "travel-agent-511710" ;;
    staging) echo "travel-agent-staging-51221" ;;
    prod)    echo "travel-agent-prod-512211" ;;
    *)
      echo "❌ Unknown environment: $1 (expected: dev | staging | prod)" >&2
      exit 1
      ;;
  esac
}

ACTION="${1:-dev}"

if [[ "${ACTION}" == "pr-check" ]]; then
  ENV_NAME="${2:-dev}"
  PROJECT_ID="$(get_project_id "${ENV_NAME}")"
  echo "🧪 Running CI PR Checks in project ${PROJECT_ID}..."
  gcloud builds submit "${REPO_ROOT}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --config="${REPO_ROOT}/.cloudbuild/pr_checks.yaml"
  exit 0
fi

ENV_NAME="${ACTION}"
PROJECT_ID="$(get_project_id "${ENV_NAME}")"
IMAGE_TAG="${IMAGE_TAG:-$(git -C "${REPO_ROOT}" rev-parse --short HEAD)}"

echo "=============================================================================="
echo "🚢 Deploying Travel Agent Platform"
echo "   Environment : ${ENV_NAME}"
echo "   GCP Project : ${PROJECT_ID}"
echo "   Region      : ${REGION}"
echo "   Image Tag   : ${IMAGE_TAG}"
echo "=============================================================================="

# 1. Ensure bootstrap prerequisites (state bucket & meta APIs) exist
"${SCRIPT_DIR}/bootstrap.sh" "${ENV_NAME}"

# 2. Submit the unified CI/CD + Terraform + Cloud Run build to Cloud Build
gcloud builds submit "${REPO_ROOT}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --config="${REPO_ROOT}/.cloudbuild/deploy.yaml" \
  --substitutions="_ENV=${ENV_NAME},_REGION=${REGION},_IMAGE_TAG=${IMAGE_TAG}"
