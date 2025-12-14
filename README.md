# Agent SaaS Platform 🚀

## 🎯 Vision

Une plateforme SaaS **B2B Multi-Tenant** permettant aux PME de créer et déployer des "Employés Numériques" (Agents IA) sans code.
L'utilisateur configure son agent (Prompt + Outils MCP) et le déploie dans son environnement (Web, Slack, etc.).

## ✨ Features V1

- 🔐 **Multi-Tenant Auth** : JWT, bcrypt, RBAC, sessions sécurisées
- 👥 **Gestion d'Équipe** : Invitations, rôles (Owner, Admin, Manager, Member, Viewer)
- 🤖 **Agents IA** : Création, configuration, prompts personnalisés
- 🔧 **Outils MCP** : Marketplace d'outils connectables
- 🔄 **Workflows** : Automatisation avec triggers et actions
- 📊 **Dashboard** : Statistiques et métriques en temps réel
- 🏢 **Périmètres Fonctionnels** : Organisation par département (Commercial, Marketing, etc.)

## 🏗️ Architecture

```
agent-saas/
├── frontend/           # Next.js 16 + React 19 + Tailwind CSS 4
├── backend/            # FastAPI + SQLAlchemy + bcrypt + JWT
│   ├── config.py       # Configuration centralisée (pydantic-settings)
│   ├── security.py     # Auth, JWT, RBAC
│   ├── database.py     # Modèles SQLAlchemy
│   ├── main.py         # API endpoints
│   └── migrations/     # Alembic migrations
└── infra/              # Docker + Terraform + CI/CD
```

## 🚀 Quick Start

### Développement (Docker)

```bash
# Démarrer l'environnement complet
docker-compose -f infra/docker-compose.yml up --build

# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Développement Local

```bash
# Backend
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
bun install
bun run dev
```

## 🔧 Configuration

Copier `.env.example` vers `.env` et configurer :

```env
# Production obligatoire
SECRET_KEY=your-super-secret-key-minimum-32-characters
DATABASE_URL=postgresql://user:pass@host:5432/db
ENVIRONMENT=production

# Optional: AI providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## 📚 Documentation

| Document | Description |
|----------|-------------|
| `AGENTS.md` | Roadmap et architecture globale |
| `frontend/AGENTS.md` | Guide frontend |
| `backend/AGENTS.md` | Guide backend |
| `infra/AGENTS.md` | Guide infrastructure |

## 🛡️ Sécurité

- ✅ Passwords hashés avec bcrypt (12 rounds)
- ✅ JWT tokens avec rotation (access + refresh)
- ✅ RBAC avec permissions granulaires
- ✅ Validation Pydantic sur tous les inputs
- ✅ CORS configuré par environnement
- ✅ Secrets via variables d'environnement

## 📜 License

MIT © 2024