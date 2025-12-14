# AGENTS.md - Infrastructure Agent

<metadata>
<component>Infrastructure</component>
<tech>Docker, Docker Compose, Terraform, GitHub Actions</tech>
<scope>Déploiement, CI/CD, IaC, Environnements</scope>
</metadata>

## 🏗️ Identité : Agent Infrastructure

Je suis l'agent spécialisé dans l'**infrastructure** de la plateforme Agent SaaS.
Mon rôle est de gérer le **déploiement**, le **CI/CD**, et l'**Infrastructure as Code**.

## 📁 Structure

```
infra/
├── docker-compose.yml       # Dev environment
├── docker-compose.prod.yml  # Production environment
└── terraform/
    ├── main.tf                  # Config Terraform principale
    ├── terraform.tfvars.example # Variables (template)
    ├── .gitignore               # Ignore secrets/state
    └── README.md                # Documentation Terraform

.github/
└── workflows/
    ├── ci-cd.yml            # Pipeline Build/Test/Deploy
    └── terraform.yml        # Infrastructure as Code
```

## 🐳 Docker

### Développement
```bash
# Démarrer l'environnement de dev
docker compose -f infra/docker-compose.yml up -d --build

# Voir les logs
docker compose -f infra/docker-compose.yml logs -f

# Arrêter
docker compose -f infra/docker-compose.yml down
```

### Production
```bash
# Avec images GitHub Container Registry
GITHUB_REPO=username/agent-saas docker compose -f infra/docker-compose.prod.yml up -d
```

### Images
| Service | Base Image | Runtime |
|---------|------------|---------|
| Frontend | `oven/bun:1-slim` | Bun + Next.js |
| Backend | `ghcr.io/astral-sh/uv:python3.11-bookworm-slim` | uv + FastAPI |

## 🔧 Terraform

### Ressources Gérées
| Ressource | Description |
|-----------|-------------|
| `github_repository` | Repository avec settings |
| `github_branch_protection` | Protection branche main |
| `github_repository_environment` | Environnements (dev/staging/prod) |
| `github_actions_secret` | Secrets CI/CD |
| `github_actions_variable` | Variables workflows |

### Commandes
```bash
cd infra/terraform

# Setup
cp terraform.tfvars.example terraform.tfvars
# Éditer terraform.tfvars avec vos valeurs

# Déployer
terraform init
terraform plan
terraform apply
```

### Variables Requises
```hcl
github_owner = "votre-username"
github_token = "ghp_xxxxx"  # Personal Access Token
```

## 🚀 GitHub Actions

### Pipeline CI/CD (`ci-cd.yml`)
```
Push/PR → Build & Test → Build Images → Deploy Staging → Deploy Prod
                ↓               ↓
           Python + Bun    ghcr.io push
```

**Jobs :**
1. `build-and-test` : Lint, tests, build
2. `build-images` : Build et push Docker vers GHCR
3. `deploy-staging` : Déploiement auto sur staging
4. `deploy-production` : Déploiement avec approbation

### Pipeline Terraform (`terraform.yml`)
```
Push/PR (infra/terraform/*) → Format → Init → Plan → Apply
```

**Triggers :**
- Auto sur push vers `infra/terraform/`
- Manuel via `workflow_dispatch`

## 🌍 Environnements

| Env | Branche | Auto-deploy | Approbation |
|-----|---------|-------------|-------------|
| Development | develop | ✅ | Non |
| Staging | main | ✅ | Non |
| Production | main | ⏸️ | Oui |

## 🔐 Secrets GitHub Actions

| Secret | Usage |
|--------|-------|
| `GITHUB_TOKEN` | Auto (push images GHCR) |
| `TF_GITHUB_TOKEN` | Terraform provider |
| `DOCKER_USERNAME` | Docker Hub (optionnel) |
| `DOCKER_PASSWORD` | Docker Hub (optionnel) |

## ⚠️ Règles Critiques

<rule id="no-secrets-commit" severity="critical">
JAMAIS de secrets dans le code.
Utiliser les GitHub Secrets ou variables d'environnement.
</rule>

<rule id="terraform-state" severity="high">
Ne JAMAIS commit `terraform.tfstate` ou `terraform.tfvars`.
Le `.gitignore` est configuré pour les ignorer.
</rule>

<rule id="image-tags" severity="medium">
Toujours tagger les images avec le SHA du commit + `latest`.
Permet le rollback facile.
</rule>

## 📋 Checklist Déploiement

### Premier déploiement
- [ ] Créer Personal Access Token GitHub (scopes: repo, workflow)
- [ ] Copier et remplir `terraform.tfvars`
- [ ] `terraform init && terraform apply`
- [ ] Push du code vers le repo créé
- [ ] Vérifier le pipeline GitHub Actions

### Déploiement quotidien
- [ ] Push vers `main` → Staging auto
- [ ] Vérifier staging
- [ ] Approuver déploiement prod dans GitHub

## 🚀 Évolutions Prévues

1. **Backend Remote Terraform** : S3/GCS pour state partagé
2. **Kubernetes** : Migration depuis Docker Compose
3. **ArgoCD** : GitOps pour déploiements K8s
4. **Monitoring** : Prometheus + Grafana
5. **Secrets Manager** : HashiCorp Vault ou AWS Secrets Manager
