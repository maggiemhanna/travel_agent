terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0, < 7.0"
    }
  }

  # Remote GCS backend. Pass -backend-config="bucket=<PROJECT_ID>-tfstate" during terraform init.
  backend "gcs" {
    prefix = "travel-agent/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
