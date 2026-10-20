output "project_id" {
  description = "Deployed GCP Project ID."
  value       = var.project_id
}

output "environment" {
  description = "Deployed environment name."
  value       = var.environment
}

output "artifact_registry_repo" {
  description = "Artifact Registry Docker repository prefix."
  value       = local.artifact_registry_prefix
}

output "runtime_service_account_email" {
  description = "Email of the least-privilege Cloud Run runtime Service Account."
  value       = google_service_account.agent_runtime.email
}

output "cicd_service_account_email" {
  description = "Email of the Cloud Build CI/CD Service Account."
  value       = google_service_account.cicd_runner.email
}

output "flights_search_url" {
  description = "Cloud Run URL for flights-search-app."
  value       = var.deploy_cloud_run_services ? google_cloud_run_v2_service.flights_search[0].uri : null
}

output "conversational_url" {
  description = "Cloud Run URL for conversational-app."
  value       = var.deploy_cloud_run_services ? google_cloud_run_v2_service.conversational[0].uri : null
}

output "frontend_url" {
  description = "Cloud Run URL for frontend."
  value       = var.deploy_cloud_run_services ? google_cloud_run_v2_service.frontend[0].uri : null
}
