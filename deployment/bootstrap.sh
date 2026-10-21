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
    staging) echo "travel-agent-staging-512211" ;;
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

  echo "1️⃣  Enabling bootstrap prerequisite APIs (for Terraform state, IAM & Cloud Build) in ${PROJECT_ID}..."
  # Note: All application & runtime APIs (Cloud Run, Artifact Registry, Vertex AI, Logging, Trace)
  # are managed declaratively by Terraform in deployment/terraform/apis.tf.
  gcloud services enable \
    serviceusage.googleapis.com \
    cloudresourcemanager.googleapis.com \
    iam.googleapis.com \
    storage.googleapis.com \
    cloudbuild.googleapis.com \
    --project="${PROJECT_ID}"

  echo "2️⃣  Ensuring Terraform remote state bucket gs://${TF_STATE_BUCKET} exists..."
  local NEEDS_IAM_PROPAGATION_WAIT=false
  if ! gcloud storage buckets describe "gs://${TF_STATE_BUCKET}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    NEEDS_IAM_PROPAGATION_WAIT=true
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

  local CICD_SA_ID="travel-agent-cicd"
  local CICD_SA="${CICD_SA_ID}@${PROJECT_ID}.iam.gserviceaccount.com"

  echo "3️⃣  Ensuring dedicated Cloud Build CI/CD Service Account (${CICD_SA}) exists..."
  if ! gcloud iam service-accounts describe "${CICD_SA}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    NEEDS_IAM_PROPAGATION_WAIT=true
    gcloud iam service-accounts create "${CICD_SA_ID}" \
      --project="${PROJECT_ID}" \
      --display-name="Travel Agent Cloud Build CI/CD SA (${ENV_NAME})" \
      --description="Dedicated Service Account for Cloud Build to execute Terraform, push images, and deploy Cloud Run."
    echo "✅ Created dedicated CI/CD Service Account ${CICD_SA}"
  else
    echo "ℹ️  Service Account ${CICD_SA} already exists."
  fi

  local CICD_ROLES=(
    "roles/serviceusage.serviceUsageAdmin"
    "roles/resourcemanager.projectIamAdmin"
    "roles/iam.serviceAccountAdmin"
    "roles/iam.serviceAccountUser"
    "roles/run.admin"
    "roles/artifactregistry.admin"
    "roles/cloudbuild.builds.editor"
    "roles/storage.admin"
    "roles/logging.logWriter"
  )

  local POLICY_LINES
  POLICY_LINES="$(gcloud projects get-iam-policy "${PROJECT_ID}" \
    --flatten="bindings[].members" \
    --format="value(bindings.role,bindings.members)")"

  echo "4️⃣  Granting CI/CD permissions strictly to ${CICD_SA}..."
  for ROLE in "${CICD_ROLES[@]}"; do
    if ! echo "${POLICY_LINES}" | grep -q "^${ROLE}[[:space:]]*serviceAccount:${CICD_SA}$"; then
      NEEDS_IAM_PROPAGATION_WAIT=true
      for attempt in 1 2 3; do
        if gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
          --member="serviceAccount:${CICD_SA}" \
          --role="${ROLE}" \
          --condition=None \
          --quiet >/dev/null 2>&1; then
          break
        fi
        sleep 2
      done
    fi
  done

  echo "5️⃣  Ensuring default Google-managed SAs (CB_SA & COMPUTE_SA) hold no extra CI/CD roles..."
  local PROJECT_NUMBER
  PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")"
  local CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
  local COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

  for SA in "${CB_SA}" "${COMPUTE_SA}"; do
    for ROLE in "${CICD_ROLES[@]}"; do
      if echo "${POLICY_LINES}" | grep -q "^${ROLE}[[:space:]]*serviceAccount:${SA}$"; then
        echo "   🧹 Removing ${ROLE} from ${SA}..."
        gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
          --member="serviceAccount:${SA}" \
          --role="${ROLE}" \
          --quiet >/dev/null 2>&1 || true
      fi
    done
  done

  if [[ "${NEEDS_IAM_PROPAGATION_WAIT}" == "true" ]]; then
    echo "⏳ Waiting 15s for newly updated IAM bindings on ${CICD_SA} to propagate..."
    sleep 15
  fi

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
