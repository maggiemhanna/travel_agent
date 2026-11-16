output "project_id" {
  description = "Deployed GCP Project ID."
  value       = var.project_id
}

output "environment" {
  description = "Deployed environment name."
  value       = var.environment
}

output "artifact_registry_repo" {
  description = "Primary Artifact Registry Docker repository prefix."
  value       = local.artifact_registry_prefix
}

output "secondary_artifact_registry_repo" {
  description = "Secondary regional Artifact Registry Docker repository prefix (null when secondary_region is disabled)."
  value       = local.enable_secondary_region ? local.secondary_artifact_registry_prefix : null
}

output "runtime_service_account_email" {
  description = "Email of the least-privilege Backend Cloud Run runtime Service Account."
  value       = google_service_account.agent_runtime.email
}

output "frontend_service_account_email" {
  description = "Email of the least-privilege Frontend Cloud Run runtime Service Account."
  value       = google_service_account.frontend_runtime.email
}

output "cicd_service_account_email" {
  description = "Email of the dedicated Cloud Build CI/CD Service Account."
  value       = data.google_service_account.cicd_runner.email
}

output "flights_search_url" {
  description = "Primary Cloud Run URL for flights-search-app."
  value       = var.deploy_cloud_run_services ? google_cloud_run_v2_service.flights_search[0].uri : null
}

output "conversational_url" {
  description = "Primary Cloud Run URL for conversational-app."
  value       = var.deploy_cloud_run_services ? google_cloud_run_v2_service.conversational[0].uri : null
}

output "frontend_url" {
  description = "Primary Cloud Run URL for frontend."
  value       = var.deploy_cloud_run_services ? google_cloud_run_v2_service.frontend[0].uri : null
}

output "flights_search_secondary_url" {
  description = "Warm secondary Cloud Run URL for flights-search-app (null when secondary_region is disabled)."
  value       = var.deploy_cloud_run_services && local.enable_secondary_region ? google_cloud_run_v2_service.flights_search_secondary[0].uri : null
}

output "conversational_secondary_url" {
  description = "Warm secondary Cloud Run URL for conversational-app (null when secondary_region is disabled)."
  value       = var.deploy_cloud_run_services && local.enable_secondary_region ? google_cloud_run_v2_service.conversational_secondary[0].uri : null
}

output "frontend_secondary_url" {
  description = "Warm secondary Cloud Run URL for frontend (null when secondary_region is disabled)."
  value       = var.deploy_cloud_run_services && local.enable_secondary_region ? google_cloud_run_v2_service.frontend_secondary[0].uri : null
}
