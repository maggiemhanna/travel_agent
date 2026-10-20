# ------------------------------------------------------------------------------
# 1. Agent Runtime Service Account (used by Cloud Run containers at runtime)
# ------------------------------------------------------------------------------
resource "google_service_account" "agent_runtime" {
  project      = var.project_id
  account_id   = "travel-agent-runtime"
  display_name = "Travel Agent Cloud Run Runtime SA (${var.environment})"
  description  = "Least-privilege runtime identity for flights-search-app and conversational-app."

  depends_on = [google_project_service.required_apis]
}

locals {
  runtime_roles = [
    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
  ]
}

resource "google_project_iam_member" "agent_runtime_roles" {
  for_each = toset(local.runtime_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}

# ------------------------------------------------------------------------------
# 2. CI/CD Cloud Build Service Account (used by Cloud Build pipelines)
# ------------------------------------------------------------------------------
resource "google_service_account" "cicd_runner" {
  project      = var.project_id
  account_id   = "travel-agent-cicd"
  display_name = "Travel Agent Cloud Build CI/CD SA (${var.environment})"
  description  = "Service Account for Cloud Build to build images and deploy to Cloud Run."

  depends_on = [google_project_service.required_apis]
}

locals {
  cicd_roles = [
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/logging.logWriter",
    "roles/storage.admin",
  ]
}

resource "google_project_iam_member" "cicd_runner_roles" {
  for_each = toset(local.cicd_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.cicd_runner.email}"
}

# Allow CI/CD SA to act as the Agent Runtime SA when deploying Cloud Run services
resource "google_service_account_iam_member" "cicd_act_as_runtime" {
  service_account_id = google_service_account.agent_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.cicd_runner.email}"
}
