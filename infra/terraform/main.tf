# =============================================================================
# Agent SaaS - Infrastructure Terraform
# =============================================================================
# Ce fichier définit l'infrastructure du projet sur GitHub
# =============================================================================

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }

  # Backend local pour commencer (peut être migré vers remote plus tard)
  backend "local" {
    path = "terraform.tfstate"
  }
}

# =============================================================================
# Provider Configuration
# =============================================================================

provider "github" {
  owner = var.github_owner
  token = var.github_token
}

# =============================================================================
# Variables
# =============================================================================

variable "github_owner" {
  description = "GitHub username or organization"
  type        = string
}

variable "github_token" {
  description = "GitHub Personal Access Token"
  type        = string
  sensitive   = true
}

variable "repository_name" {
  description = "Name of the GitHub repository"
  type        = string
  default     = "agent-saas"
}

variable "repository_description" {
  description = "Description of the repository"
  type        = string
  default     = "🤖 Usine à Employés Numériques - Plateforme SaaS d'automatisation IA"
}

variable "repository_visibility" {
  description = "Repository visibility (public or private)"
  type        = string
  default     = "private"
}

# =============================================================================
# GitHub Repository
# =============================================================================

resource "github_repository" "agent_saas" {
  name        = var.repository_name
  description = var.repository_description
  visibility  = var.repository_visibility

  # Features
  has_issues      = true
  has_projects    = true
  has_wiki        = false
  has_downloads   = false
  has_discussions = false

  # Settings
  auto_init            = false
  allow_merge_commit   = true
  allow_squash_merge   = true
  allow_rebase_merge   = false
  delete_branch_on_merge = true

  # Security
  vulnerability_alerts = true

  # Topics/Tags
  topics = [
    "saas",
    "ai",
    "automation",
    "nextjs",
    "fastapi",
    "mcp",
    "langchain",
    "docker"
  ]
}

# =============================================================================
# Branch Protection (main)
# =============================================================================

resource "github_branch_protection" "main" {
  repository_id = github_repository.agent_saas.node_id
  pattern       = "main"

  # Require PR before merging
  required_pull_request_reviews {
    required_approving_review_count = 0  # Solo dev, pas besoin d'approbation
    dismiss_stale_reviews           = true
  }

  # Require status checks
  required_status_checks {
    strict   = true
    contexts = ["build-and-test"]
  }

  # Allow force push for solo dev (can be disabled later)
  allows_force_pushes = true
  allows_deletions    = false

  # Enforce for admins too
  enforce_admins = false
}

# =============================================================================
# Repository Secrets for CI/CD
# =============================================================================

# Docker Hub credentials (optionnel, pour push des images)
resource "github_actions_secret" "docker_username" {
  count           = var.docker_username != "" ? 1 : 0
  repository      = github_repository.agent_saas.name
  secret_name     = "DOCKER_USERNAME"
  plaintext_value = var.docker_username
}

resource "github_actions_secret" "docker_password" {
  count           = var.docker_password != "" ? 1 : 0
  repository      = github_repository.agent_saas.name
  secret_name     = "DOCKER_PASSWORD"
  plaintext_value = var.docker_password
}

variable "docker_username" {
  description = "Docker Hub username (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "docker_password" {
  description = "Docker Hub password/token (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

# =============================================================================
# Repository Environments
# =============================================================================

resource "github_repository_environment" "development" {
  repository  = github_repository.agent_saas.name
  environment = "development"
}

resource "github_repository_environment" "staging" {
  repository  = github_repository.agent_saas.name
  environment = "staging"

  reviewers {
    users = []  # Ajouter des user IDs si besoin d'approbation
  }

  deployment_branch_policy {
    protected_branches     = false
    custom_branch_policies = true
  }
}

resource "github_repository_environment" "production" {
  repository  = github_repository.agent_saas.name
  environment = "production"

  reviewers {
    users = []  # Ajouter des user IDs si besoin d'approbation
  }

  deployment_branch_policy {
    protected_branches     = true
    custom_branch_policies = false
  }
}

# =============================================================================
# GitHub Actions Variables
# =============================================================================

resource "github_actions_variable" "api_url_dev" {
  repository    = github_repository.agent_saas.name
  variable_name = "API_URL_DEV"
  value         = "http://localhost:8000"
}

resource "github_actions_variable" "api_url_staging" {
  repository    = github_repository.agent_saas.name
  variable_name = "API_URL_STAGING"
  value         = "https://staging-api.agent-saas.com"
}

resource "github_actions_variable" "api_url_prod" {
  repository    = github_repository.agent_saas.name
  variable_name = "API_URL_PROD"
  value         = "https://api.agent-saas.com"
}

# =============================================================================
# Outputs
# =============================================================================

output "repository_url" {
  description = "URL of the GitHub repository"
  value       = github_repository.agent_saas.html_url
}

output "repository_clone_url" {
  description = "Clone URL (SSH)"
  value       = github_repository.agent_saas.ssh_clone_url
}

output "repository_https_url" {
  description = "Clone URL (HTTPS)"
  value       = github_repository.agent_saas.http_clone_url
}
