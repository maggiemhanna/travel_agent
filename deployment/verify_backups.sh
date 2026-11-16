#!/usr/bin/env bash
# ==============================================================================
# Non-Destructive Infrastructure Backup & Restore Verification Drill
#
# Note on Stateless Scope: All runtime Cloud Run microservices use ephemeral
# per-request InMemorySessionService() with zero persistent user database.
# Stateful platform assets requiring backup/restore verification are:
#   1. Versioned GCS Terraform Remote State (gs://<PROJECT_ID>-tfstate)
#   2. Artifact Registry Docker Image Rollback History (keep_count = 15)
#
# Usage:
#   ./deployment/verify_backups.sh --local-self-test
#   ./deployment/verify_backups.sh --env prod
#   ./deployment/verify_backups.sh --env staging
# ==============================================================================
set -euo pipefail

MODE="gcp"
ENV_NAME="prod"
REGION="${REGION:-europe-west9}"
SECONDARY_REGION="${SECONDARY_REGION:-europe-west1}"
REPOSITORY_ID="${REPOSITORY_ID:-travel-agent}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local-self-test)
      MODE="local-self-test"
      shift
      ;;
    --env)
      ENV_NAME="${2:?Missing value for --env}"
      shift 2
      ;;
    -h|--help)
      sed -n '2,15p' "$0"
      exit 0
      ;;
    *)
      echo "❌ Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

get_project_id() {
  case "$1" in
    dev)     echo "travel-agent-511710" ;;
    staging) echo "travel-agent-staging-512211" ;;
    prod)    echo "travel-agent-prod-512211" ;;
    *)
      echo "❌ Unknown environment: $1 (expected: dev | staging | prod)" >&2
      exit 1
      ;;
  esac
}

validate_tfstate_file() {
  local tfstate_path="$1"
  python3 - "${tfstate_path}" <<'PYEOF'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    state = json.load(fh)

if not isinstance(state, dict):
    raise SystemExit("❌ Restored .tfstate root must be a JSON object")

version = state.get("version")
lineage = state.get("lineage")
serial = state.get("serial")
resources = state.get("resources")

if not isinstance(version, int) or version < 4:
    raise SystemExit(f"❌ Invalid Terraform state version: {version} (expected >= 4)")
if not isinstance(lineage, str) or not lineage.strip():
    raise SystemExit("❌ Missing or empty Terraform state 'lineage' UUID")
if not isinstance(serial, int) or serial < 0:
    raise SystemExit(f"❌ Invalid Terraform state 'serial': {serial}")
if not isinstance(resources, list):
    raise SystemExit("❌ Invalid Terraform state 'resources' array")

print(
    f"   ✅ Restored .tfstate verified: format_v={version}, serial={serial}, "
    f"lineage={lineage}, managed_resources={len(resources)}"
)
PYEOF
}

if [[ "${MODE}" == "local-self-test" ]]; then
  echo "=============================================================================="
  echo "🧪 Running Backup & Restore Verification Local Self-Test"
  echo "=============================================================================="
  WORK_DIR="$(mktemp -d)"
  trap 'rm -rf "${WORK_DIR}"' EXIT

  MOCK_BUCKET_DIR="${WORK_DIR}/mock-gcs-tfstate"
  RESTORE_DIR="${WORK_DIR}/restore-drill"
  mkdir -p "${MOCK_BUCKET_DIR}" "${RESTORE_DIR}"

  cat <<'JSON' > "${MOCK_BUCKET_DIR}/default.tfstate.gen1700000001"
{
  "version": 4,
  "terraform_version": "1.9.8",
  "serial": 11,
  "lineage": "9f82c1d0-4a12-4c9a-9c5d-001122334455",
  "outputs": {},
  "resources": [
    {"mode": "managed", "type": "google_artifact_registry_repository", "name": "docker_repo"}
  ]
}
JSON

  cat <<'JSON' > "${MOCK_BUCKET_DIR}/default.tfstate.gen1700000002"
{
  "version": 4,
  "terraform_version": "1.9.8",
  "serial": 12,
  "lineage": "9f82c1d0-4a12-4c9a-9c5d-001122334455",
  "outputs": {
    "frontend_url": {"value": "https://frontend-paris.a.run.app", "type": "string"}
  },
  "resources": [
    {"mode": "managed", "type": "google_artifact_registry_repository", "name": "docker_repo"},
    {"mode": "managed", "type": "google_cloud_run_v2_service", "name": "flights_search"},
    {"mode": "managed", "type": "google_cloud_run_v2_service", "name": "conversational"},
    {"mode": "managed", "type": "google_cloud_run_v2_service", "name": "frontend"}
  ]
}
JSON

  cat <<'JSON' > "${MOCK_BUCKET_DIR}/corrupted.tfstate"
{"version": 4, "serial": 1, "lineage": "", "resources": "broken"}
JSON

  echo "1️⃣  Simulating non-destructive restore of prior generation (#1700000001) and latest (#1700000002)..."
  cp "${MOCK_BUCKET_DIR}/default.tfstate.gen1700000001" "${RESTORE_DIR}/restored_prev.tfstate"
  cp "${MOCK_BUCKET_DIR}/default.tfstate.gen1700000002" "${RESTORE_DIR}/restored_latest.tfstate"

  validate_tfstate_file "${RESTORE_DIR}/restored_prev.tfstate"
  validate_tfstate_file "${RESTORE_DIR}/restored_latest.tfstate"

  echo "2️⃣  Verifying integrity validator rejects corrupted state snapshots..."
  if validate_tfstate_file "${MOCK_BUCKET_DIR}/corrupted.tfstate" >/dev/null 2>&1; then
    echo "❌ Validator failed to reject corrupted .tfstate!" >&2
    exit 1
  fi
  echo "   ✅ Corrupted .tfstate snapshot accurately rejected"

  echo "3️⃣  Verifying recovery runbook command synthesis..."
  SAMPLE_BUCKET="gs://travel-agent-prod-512211-tfstate/travel-agent/state/default.tfstate"
  echo "   📋 Rollback command: gcloud storage cp \"${SAMPLE_BUCKET}#1700000001\" \"${SAMPLE_BUCKET}\""
  echo "✅ Backup & restore local self-test passed!"
  exit 0
fi

PROJECT_ID="$(get_project_id "${ENV_NAME}")"
TF_STATE_BUCKET="${PROJECT_ID}-tfstate"
STATE_OBJECT="gs://${TF_STATE_BUCKET}/travel-agent/state/default.tfstate"

RESTORE_TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${RESTORE_TMP_DIR}"' EXIT

echo "=============================================================================="
echo "🗄️  Verifying Infrastructure Backups & Non-Destructive Restore [${ENV_NAME}]"
echo "   GCP Project : ${PROJECT_ID}"
echo "   State URI   : ${STATE_OBJECT}"
echo "=============================================================================="

echo "1️⃣  Checking GCS Object Versioning on gs://${TF_STATE_BUCKET}..."
VERSIONING_ENABLED="$(gcloud storage buckets describe "gs://${TF_STATE_BUCKET}" \
  --project="${PROJECT_ID}" \
  --format="value(versioning.enabled)")"
if [[ "${VERSIONING_ENABLED}" != "True" && "${VERSIONING_ENABLED}" != "true" ]]; then
  echo "❌ Object versioning is NOT enabled on gs://${TF_STATE_BUCKET}!" >&2
  exit 1
fi
echo "   ✅ Object versioning is enabled on gs://${TF_STATE_BUCKET}"

echo "2️⃣  Listing archived .tfstate generations..."
GENERATIONS="$(gcloud storage ls -a "${STATE_OBJECT}" --project="${PROJECT_ID}" | grep '#' || true)"
if [[ -z "${GENERATIONS}" ]]; then
  echo "❌ No versioned state objects found at ${STATE_OBJECT}" >&2
  exit 1
fi
GEN_COUNT="$(echo "${GENERATIONS}" | wc -l | tr -d ' ')"
LATEST_GEN_URI="$(echo "${GENERATIONS}" | tail -n 1 | awk '{print $1}')"
PREV_GEN_URI="$(echo "${GENERATIONS}" | tail -n 2 | head -n 1 | awk '{print $1}')"
echo "   ✅ Found ${GEN_COUNT} state generation(s). Target drill snapshot: ${PREV_GEN_URI}"

echo "3️⃣  Performing non-destructive restore drill into isolated temp directory..."
gcloud storage cp "${PREV_GEN_URI}" "${RESTORE_TMP_DIR}/restored.tfstate" --project="${PROJECT_ID}" --quiet
validate_tfstate_file "${RESTORE_TMP_DIR}/restored.tfstate"

echo "4️⃣  Checking Artifact Registry container rollback tags (keep_count = 15 policy)..."
SERVICES=("flights-search-app" "conversational-app" "frontend")
REGIONS_TO_CHECK=("${REGION}")
if [[ "${ENV_NAME}" == "prod" && -n "${SECONDARY_REGION}" && "${SECONDARY_REGION}" != "${REGION}" ]]; then
  REGIONS_TO_CHECK+=("${SECONDARY_REGION}")
fi

for reg in "${REGIONS_TO_CHECK[@]}"; do
  REPO_PREFIX="${reg}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_ID}"
  for svc in "${SERVICES[@]}"; do
    TAG_COUNT="$(gcloud artifacts docker images list "${REPO_PREFIX}/${svc}" \
      --include-tags \
      --project="${PROJECT_ID}" \
      --format="value(version)" 2>/dev/null | wc -l | tr -d ' ')"
    if [[ "${TAG_COUNT}" -lt 1 ]]; then
      echo "❌ No rollback container images found for ${REPO_PREFIX}/${svc}" >&2
      exit 1
    fi
    echo "   ✅ ${REPO_PREFIX}/${svc}: ${TAG_COUNT} retained image version(s)"
  done
done

echo ""
echo "📋 Emergency State Rollback Runbook (non-destructive reference):"
echo "   gcloud storage cp \"${PREV_GEN_URI}\" \"${STATE_OBJECT}\" --project=\"${PROJECT_ID}\""
echo "✅ Infrastructure Backup & Restore Verification completed successfully!"
