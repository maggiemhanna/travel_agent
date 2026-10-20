#!/usr/bin/env bash
# ==============================================================================
# Bootstrap GCP Project(s) for Terraform & Cloud Build
# Usage:
#   ./deployment/bootstrap.sh dev       # Bootstrap travel-agent-511710
#   ./deployment/bootstrap.sh staging   # Bootstrap travel-agent-staging-51221
#   ./deployment/bootstrap.sh prod      # Bootstrap travel-agent-prod-512211
#   ./deployment/bootstrap.sh all       # Bootstrap all three environments
# ==============================================================================
set -euo pipefail

REGION="${REGION:-europe-west9}"

get_project_id() {
  case "$1" in
    dev)     echo "travel-agent-511710" ;;
    staging) echo "travel-agent-staging-51221" ;;
    prod)    echo "travel-agent-prod-512211" ;;
    *)
      echo "❌ Unknown environment: $1 (expected: dev | staging | prod | all)" >&2
      exit 1
      ;;
  esac
}

bootstrap_project() {
  local ENV_NAME="$1"
  local PROJECT_ID
  PROJECT_ID="$(get_project_id "$ENV_NAME")"
  local TF_STATE_BUCKET="${PROJECT_ID}-tfstate"

  echo "=============================================================================="
  echo "🚀 Bootstrapping [${ENV_NAME}] -> Project: ${PROJECT_ID} (Region: ${REGION})"
  echo "=============================================================================="

  echo "1️⃣  Enabling bootstrap prerequisite APIs (for Terraform state & Cloud Build) in ${PROJECT_ID}..."
  # Note: All application & runtime APIs (Cloud Run, Artifact Registry, Vertex AI, IAM, Logging, Trace)
  # are managed declaratively by Terraform in deployment/terraform/apis.tf.
  gcloud services enable \
    serviceusage.googleapis.com \
    cloudresourcemanager.googleapis.com \
    storage.googleapis.com \
    cloudbuild.googleapis.com \
    --project="${PROJECT_ID}"

  echo "2️⃣  Ensuring Terraform remote state bucket gs://${TF_STATE_BUCKET} exists..."
  if ! gcloud storage buckets describe "gs://${TF_STATE_BUCKET}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud storage buckets create "gs://${TF_STATE_BUCKET}" \
      --project="${PROJECT_ID}" \
      --location="${REGION}" \
      --uniform-bucket-level-access
    gcloud storage buckets update "gs://${TF_STATE_BUCKET}" \
      --project="${PROJECT_ID}" \
      --versioning
    echo "✅ Created versioned state bucket gs://${TF_STATE_BUCKET}"
  else
    echo "ℹ️  Bucket gs://${TF_STATE_BUCKET} already exists."
  fi

  echo "3️⃣  Granting Cloud Build service accounts permissions to execute Terraform..."
  local PROJECT_NUMBER
  PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")"
  local CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
  local COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

  for SA in "${CB_SA}" "${COMPUTE_SA}"; do
    for ROLE in \
      "roles/serviceusage.serviceUsageAdmin" \
      "roles/resourcemanager.projectIamAdmin" \
      "roles/iam.serviceAccountAdmin" \
      "roles/iam.serviceAccountUser" \
      "roles/run.admin" \
      "roles/artifactregistry.admin" \
      "roles/storage.admin" \
      "roles/logging.logWriter"; do
      gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
        --member="serviceAccount:${SA}" \
        --role="${ROLE}" \
        --condition=None \
        --quiet >/dev/null || true
    done
  done

  echo "✅ Bootstrap complete for [${ENV_NAME}] (${PROJECT_ID})!"
  echo
}

TARGET="${1:-dev}"

if [[ "${TARGET}" == "all" ]]; then
  for env in dev staging prod; do
    bootstrap_project "${env}"
  done
else
  bootstrap_project "${TARGET}"
fi
