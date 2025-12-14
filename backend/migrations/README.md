# Agent SaaS Database Migrations

Ce dossier contient les migrations Alembic pour gérer les changements de schéma de base de données.

## Commandes utiles

```bash
# Créer une nouvelle migration (auto-génère à partir des modèles)
alembic revision --autogenerate -m "Description du changement"

# Appliquer toutes les migrations
alembic upgrade head

# Voir l'historique des migrations
alembic history

# Voir la migration actuelle
alembic current

# Revenir en arrière d'une migration
alembic downgrade -1

# Revenir à une migration spécifique
alembic downgrade <revision_id>
```

## Structure

- `env.py` - Configuration de l'environnement Alembic
- `script.py.mako` - Template pour les nouveaux fichiers de migration
- `versions/` - Dossier contenant les fichiers de migration
