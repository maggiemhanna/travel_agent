# ------------------------------------------------------------------------------
# 1. Backend Agent Runtime Service Account (flights-search-app & conversational-app)
# ------------------------------------------------------------------------------
resource "google_service_account" "agent_runtime" {
  project      = var.project_id
  account_id   = "travel-agent-runtime"
  display_name = "Travel Agent Backend Runtime SA (${var.environment})"
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
# 2. Frontend Runtime Service Account (frontend static Nginx container)
# ------------------------------------------------------------------------------
resource "google_service_account" "frontend_runtime" {
  project      = var.project_id
  account_id   = "travel-agent-frontend"
  display_name = "Travel Agent Frontend Runtime SA (${var.environment})"
  description  = "Minimal runtime identity for frontend (no Vertex AI or admin access)."

  depends_on = [google_project_service.required_apis]
}

locals {
  frontend_roles = [
    "roles/logging.logWriter",
  ]
}

resource "google_project_iam_member" "frontend_runtime_roles" {
  for_each = toset(local.frontend_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.frontend_runtime.email}"
}

# ------------------------------------------------------------------------------
# 3. CI/CD Cloud Build Service Account (bootstrapped by deployment/bootstrap.sh)
# ------------------------------------------------------------------------------
data "google_service_account" "cicd_runner" {
  project    = var.project_id
  account_id = "travel-agent-cicd"
}

# Hand off ownership of travel-agent-cicd from Terraform state to bootstrap.sh
# without deleting the active CI/CD Service Account during upgrades.
removed {
  from = google_service_account.cicd_runner

  lifecycle {
    destroy = false
  }
}

removed {
  from = google_project_iam_member.cicd_runner_roles

  lifecycle {
    destroy = false
  }
}

# Allow CI/CD SA to attach the Backend and Frontend Runtime SAs to Cloud Run
resource "google_service_account_iam_member" "cicd_act_as_runtime" {
  service_account_id = google_service_account.agent_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${data.google_service_account.cicd_runner.email}"
}

resource "google_service_account_iam_member" "cicd_act_as_frontend" {
  service_account_id = google_service_account.frontend_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${data.google_service_account.cicd_runner.email}"
}
