resource "google_artifact_registry_repository" "docker_repo" {
  project       = var.project_id
  location      = var.region
  repository_id = var.repository_id
  description   = "Docker repository for Travel Agent microservices (${var.environment})"
  format        = "DOCKER"

  cleanup_policies {
    id     = "keep-recent-versions"
    action = "KEEP"
    most_recent_versions {
      keep_count = 15
    }
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_artifact_registry_repository" "docker_repo_secondary" {
  count         = local.enable_secondary_region ? 1 : 0
  project       = var.project_id
  location      = var.secondary_region
  repository_id = var.repository_id
  description   = "Secondary warm-region Docker repository for Travel Agent microservices (${var.environment})"
  format        = "DOCKER"

  cleanup_policies {
    id     = "keep-recent-versions"
    action = "KEEP"
    most_recent_versions {
      keep_count = 15
    }
  }

  depends_on = [google_project_service.required_apis]
}

locals {
  enable_secondary_region            = var.secondary_region != "" && var.secondary_region != var.region
  artifact_registry_prefix           = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}"
  secondary_artifact_registry_prefix = local.enable_secondary_region ? "${var.secondary_region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo_secondary[0].repository_id}" : ""
}
