# 🏗️ Infrastructure Terraform - Agent SaaS

Ce dossier contient la configuration Terraform pour gérer l'infrastructure du projet.

## 📁 Structure

```
terraform/
├── main.tf                    # Configuration principale
├── terraform.tfvars.example   # Exemple de variables (à copier)
├── .gitignore                 # Ignore les secrets et state
└── README.md                  # Ce fichier
```

## 🚀 Démarrage rapide

### 1. Prérequis

- [Terraform](https://www.terraform.io/downloads) >= 1.0.0
- Un compte GitHub
- Un [Personal Access Token GitHub](https://github.com/settings/tokens)

### 2. Configuration

```bash
# Aller dans le dossier terraform
cd infra/terraform

# Copier le fichier d'exemple
cp terraform.tfvars.example terraform.tfvars

# Éditer avec vos valeurs
nano terraform.tfvars
```

**Variables requises dans `terraform.tfvars` :**

```hcl
github_owner = "votre-username-github"
github_token = "ghp_xxxxxxxxxxxxxxxxxxxx"
```

### 3. Créer le token GitHub

1. Allez sur https://github.com/settings/tokens
2. Cliquez "Generate new token (classic)"
3. Sélectionnez les scopes :
   - `repo` (accès complet aux repos)
   - `workflow` (pour GitHub Actions)
   - `admin:repo_hook` (pour les webhooks)
4. Copiez le token dans `terraform.tfvars`

### 4. Déployer

```bash
# Initialiser Terraform
terraform init

# Voir le plan des changements
terraform plan

# Appliquer les changements
terraform apply
```

## 📋 Ressources créées

| Ressource | Description |
|-----------|-------------|
| `github_repository` | Repository GitHub avec topics et settings |
| `github_branch_protection` | Protection de la branche main |
| `github_repository_environment` | Environnements (dev, staging, prod) |
| `github_actions_secret` | Secrets pour CI/CD (optionnel) |
| `github_actions_variable` | Variables pour les workflows |

## 🔐 Sécurité

⚠️ **Important :**
- Ne commitez JAMAIS `terraform.tfvars` avec vos secrets
- Le fichier `.gitignore` protège déjà ces fichiers
- Utilisez des variables d'environnement en CI/CD

## 🔄 CI/CD avec GitHub Actions

Deux workflows sont configurés :

### 1. `ci-cd.yml` - Pipeline principal
- Build & Test (Python + Next.js)
- Build des images Docker
- Push vers GitHub Container Registry
- Deploy staging puis production

### 2. `terraform.yml` - Infrastructure
- Format check
- Plan sur les PR
- Apply automatique sur main
- Destroy manuel si besoin

## 🎛️ Commandes utiles

```bash
# Voir l'état actuel
terraform show

# Lister les ressources
terraform state list

# Détruire l'infrastructure
terraform destroy

# Formater les fichiers
terraform fmt -recursive

# Valider la syntaxe
terraform validate
```

## 🌍 Environnements

| Environnement | Branche | Auto-deploy |
|---------------|---------|-------------|
| Development | develop | ✅ |
| Staging | main | ✅ |
| Production | main | ⏸️ (approbation requise) |

## 📝 Notes

- Le state Terraform est stocké localement par défaut
- Pour un usage en équipe, configurez un backend remote (S3, GCS, Terraform Cloud)
- Les images Docker sont poussées vers GitHub Container Registry (ghcr.io)
