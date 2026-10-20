variable "project_id" {
  description = "Google Cloud Project ID for the target environment (dev, staging, or prod)."
  type        = string
}

variable "environment" {
  description = "Deployment environment name (dev, staging, prod)."
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "region" {
  description = "Google Cloud region for Cloud Run, Artifact Registry, and Vertex AI."
  type        = string
  default     = "europe-west9"
}

variable "repository_id" {
  description = "Artifact Registry Docker repository ID."
  type        = string
  default     = "travel-agent"
}

variable "image_tag" {
  description = "Container image tag to deploy across all three services (e.g., commit SHA or latest)."
  type        = string
  default     = "latest"
}

variable "deploy_cloud_run_services" {
  description = "Whether to provision Cloud Run services. Set to false on initial bootstrap before Docker images are pushed, then true."
  type        = bool
  default     = true
}

variable "min_instances" {
  description = "Minimum number of Cloud Run instances per service (0 for dev/staging, >=1 for prod)."
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of Cloud Run instances per service."
  type        = number
  default     = 10
}

variable "backend_cpu" {
  description = "CPU allocation for backend ADK Cloud Run services."
  type        = string
  default     = "2"
}

variable "backend_memory" {
  description = "Memory allocation for backend ADK Cloud Run services."
  type        = string
  default     = "2Gi"
}

variable "frontend_cpu" {
  description = "CPU allocation for the frontend Nginx Cloud Run service."
  type        = string
  default     = "1"
}

variable "frontend_memory" {
  description = "Memory allocation for the frontend Nginx Cloud Run service."
  type        = string
  default     = "512Mi"
}

variable "allow_public_access" {
  description = "Allow unauthenticated public HTTP invocation of the Cloud Run services."
  type        = bool
  default     = true
}

variable "allowed_origins" {
  description = "Comma-separated list of allowed CORS origins for backend services."
  type        = string
  default     = "*"
}
