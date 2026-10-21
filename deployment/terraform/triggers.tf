# ==============================================================================
# Cloud Build Git Triggers (PR Checks, Staging on merge to main, Prod on v* tag)
# Enabled when var.enable_cloudbuild_triggers = true and GitHub repo is linked.
# ==============================================================================

# 1. PR Checks Trigger (runs on Pull Requests targeting `main` in dev/staging)
resource "google_cloudbuild_trigger" "pr_checks" {
  count           = var.enable_cloudbuild_triggers && var.environment != "prod" ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "travel-agent-pr-checks"
  description     = "Run unit tests, frontend build, and Terraform validation on Pull Requests to main"
  filename        = ".cloudbuild/pr_checks.yaml"
  service_account = "projects/${var.project_id}/serviceAccounts/${data.google_service_account.cicd_runner.email}"

  github {
    owner = var.github_owner
    name  = var.github_repo
    pull_request {
      branch = "^main$"
    }
  }

  depends_on = [google_project_service.required_apis]
}

# 2. CD Staging Trigger (runs automatically on push/merge to `main` in staging project)
resource "google_cloudbuild_trigger" "cd_staging" {
  count           = var.enable_cloudbuild_triggers && var.environment == "staging" ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "travel-agent-cd-staging"
  description     = "Continuous Deployment to Staging on merge to main"
  filename        = ".cloudbuild/staging.yaml"
  service_account = "projects/${var.project_id}/serviceAccounts/${data.google_service_account.cicd_runner.email}"

  github {
    owner = var.github_owner
    name  = var.github_repo
    push {
      branch = "^main$"
    }
  }

  depends_on = [google_project_service.required_apis]
}

# 3. CD Production Trigger (runs on `v*` Git tag with manual approval gate in prod project)
resource "google_cloudbuild_trigger" "cd_prod" {
  count           = var.enable_cloudbuild_triggers && var.environment == "prod" ? 1 : 0
  project         = var.project_id
  location        = var.region
  name            = "travel-agent-cd-prod"
  description     = "Production release pipeline triggered on v* tag with manual approval gate"
  filename        = ".cloudbuild/prod.yaml"
  service_account = "projects/${var.project_id}/serviceAccounts/${data.google_service_account.cicd_runner.email}"

  approval_config {
    approval_required = true
  }

  github {
    owner = var.github_owner
    name  = var.github_repo
    push {
      tag = "^v[0-9]+\\.[0-9]+\\.[0-9]+.*$"
    }
  }

  depends_on = [google_project_service.required_apis]
}
