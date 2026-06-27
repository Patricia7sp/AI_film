# ============================================================
# Terraform Configuration for GitHub Secrets
# Gerencia secrets do repositório de forma automatizada
# ============================================================

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 5.0"
    }
  }
}

# ============================================================
# Provider Configuration
# ============================================================

provider "github" {
  token = var.github_token
  owner = var.github_owner
}

# ============================================================
# Variables
# ============================================================

variable "github_token" {
  description = "GitHub Personal Access Token com permissão 'repo'"
  type        = string
  sensitive   = true
}

variable "github_owner" {
  description = "Owner do repositório GitHub"
  type        = string
  default     = "Patricia7sp"
}

variable "github_repository" {
  description = "Nome do repositório GitHub"
  type        = string
  default     = "AI_film"
}

variable "gemini_api_key" {
  description = "Google Gemini API Key"
  type        = string
  sensitive   = true
  default     = "AIzaSyD6L3PQI5MSmiQvosOrhcQllU4_O3UplP4"
}

variable "openai_api_key" {
  description = "OpenAI API Key (Fallback)"
  type        = string
  sensitive   = true
  default     = ""  # Opcional - já existe no GitHub
}

variable "elevenlabs_api_key" {
  description = "ElevenLabs API Key"
  type        = string
  sensitive   = true
  default     = ""  # Opcional - já existe no GitHub
}

variable "stability_api_key" {
  description = "Stability AI API Key"
  type        = string
  sensitive   = true
  default     = ""  # Opcional - já existe no GitHub
}

variable "replicate_api_token" {
  description = "Replicate API Token"
  type        = string
  sensitive   = true
  default     = ""  # Opcional - já existe no GitHub
}

# ============================================================
# GitHub Repository Secrets
# ============================================================

# Gemini API Key (Principal LLM)
resource "github_actions_secret" "gemini_api_key" {
  repository      = var.github_repository
  secret_name     = "GEMINI_API_KEY"
  plaintext_value = var.gemini_api_key
}

# OpenAI API Key (Fallback) - Opcional
resource "github_actions_secret" "openai_api_key" {
  count           = var.openai_api_key != "" ? 1 : 0
  repository      = var.github_repository
  secret_name     = "OPENAI_API_KEY"
  plaintext_value = var.openai_api_key
}

# ElevenLabs API Key - Opcional
resource "github_actions_secret" "elevenlabs_api_key" {
  count           = var.elevenlabs_api_key != "" ? 1 : 0
  repository      = var.github_repository
  secret_name     = "ELEVENLABS_API_KEY"
  plaintext_value = var.elevenlabs_api_key
}

# Stability AI API Key - Opcional
resource "github_actions_secret" "stability_api_key" {
  count           = var.stability_api_key != "" ? 1 : 0
  repository      = var.github_repository
  secret_name     = "STABILITY_API_KEY"
  plaintext_value = var.stability_api_key
}

# Replicate API Token - Opcional
resource "github_actions_secret" "replicate_api_token" {
  count           = var.replicate_api_token != "" ? 1 : 0
  repository      = var.github_repository
  secret_name     = "REPLICATE_API_TOKEN"
  plaintext_value = var.replicate_api_token
}

# ============================================================
# Outputs
# ============================================================

output "secrets_created" {
  description = "Lista de secrets criados"
  value = [
    "GEMINI_API_KEY",
    var.openai_api_key != "" ? "OPENAI_API_KEY" : null,
    var.elevenlabs_api_key != "" ? "ELEVENLABS_API_KEY" : null,
    var.stability_api_key != "" ? "STABILITY_API_KEY" : null,
    var.replicate_api_token != "" ? "REPLICATE_API_TOKEN" : null,
  ]
}

output "repository_url" {
  description = "URL do repositório"
  value       = "https://github.com/${var.github_owner}/${var.github_repository}"
}

output "secrets_url" {
  description = "URL para visualizar secrets"
  value       = "https://github.com/${var.github_owner}/${var.github_repository}/settings/secrets/actions"
}
