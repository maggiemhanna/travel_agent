# ------------------------------------------------------------------------------
# 1. Flights Search Backend Service (flights-search-app)
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "flights_search" {
  count                = var.deploy_cloud_run_services ? 1 : 0
  project              = var.project_id
  name                 = "flights-search-app"
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = var.allow_public_access
  deletion_protection  = var.environment == "prod"

  template {
    service_account = google_service_account.agent_runtime.email
    timeout         = "300s"

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = "${local.artifact_registry_prefix}/flights-search-app:${var.image_tag}"

      resources {
        limits = {
          cpu    = var.backend_cpu
          memory = var.backend_memory
        }
        cpu_idle = var.min_instances == 0
      }

      ports {
        container_port = 8080
      }

      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "1"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "GOOGLE_API_USE_MTLS"
        value = "never"
      }
      env {
        name  = "GOOGLE_API_USE_CLIENT_CERTIFICATE"
        value = "false"
      }
      env {
        name  = "FLIGHTS_SEARCH_MODEL"
        value = var.flights_search_model
      }
      env {
        name  = "GEMINI_MODEL_LOCATION"
        value = var.gemini_model_location
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = var.allowed_origins
      }
    }
  }

  depends_on = [
    google_project_service.required_apis,
    google_artifact_registry_repository.docker_repo,
    google_project_iam_member.agent_runtime_roles,
  ]
}

# ------------------------------------------------------------------------------
# 2. Conversational Multi-Agent Workflow Service (conversational-app)
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "conversational" {
  count                = var.deploy_cloud_run_services ? 1 : 0
  project              = var.project_id
  name                 = "conversational-app"
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = var.allow_public_access
  deletion_protection  = var.environment == "prod"

  template {
    service_account = google_service_account.agent_runtime.email
    timeout         = "300s"

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = "${local.artifact_registry_prefix}/conversational-app:${var.image_tag}"

      resources {
        limits = {
          cpu    = var.backend_cpu
          memory = var.backend_memory
        }
        cpu_idle = var.min_instances == 0
      }

      ports {
        container_port = 8080
      }

      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "1"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "GOOGLE_API_USE_MTLS"
        value = "never"
      }
      env {
        name  = "GOOGLE_API_USE_CLIENT_CERTIFICATE"
        value = "false"
      }
      env {
        name  = "CONVERSATIONAL_MODEL"
        value = var.conversational_model
      }
      env {
        name  = "GEMINI_MODEL_LOCATION"
        value = var.gemini_model_location
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = var.allowed_origins
      }
    }
  }

  depends_on = [
    google_project_service.required_apis,
    google_artifact_registry_repository.docker_repo,
    google_project_iam_member.agent_runtime_roles,
  ]
}

# ------------------------------------------------------------------------------
# 3. React + Nginx Frontend Service (frontend)
# ------------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "frontend" {
  count                = var.deploy_cloud_run_services ? 1 : 0
  project              = var.project_id
  name                 = "frontend"
  location             = var.region
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = var.allow_public_access
  deletion_protection  = var.environment == "prod"

  template {
    service_account = google_service_account.frontend_runtime.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = "${local.artifact_registry_prefix}/frontend:${var.image_tag}"

      resources {
        limits = {
          cpu    = var.frontend_cpu
          memory = var.frontend_memory
        }
        cpu_idle = true
      }

      ports {
        container_port = 8080
      }

      # Automatically wire the deployed Cloud Run backend URLs at runtime
      env {
        name  = "VITE_FLIGHTS_SEARCH_API_URL"
        value = google_cloud_run_v2_service.flights_search[0].uri
      }
      env {
        name  = "VITE_CONVERSATIONAL_API_URL"
        value = google_cloud_run_v2_service.conversational[0].uri
      }
    }
  }

  depends_on = [
    google_cloud_run_v2_service.flights_search,
    google_cloud_run_v2_service.conversational,
    google_project_iam_member.frontend_runtime_roles,
    google_service_account_iam_member.cicd_act_as_frontend,
  ]
}

