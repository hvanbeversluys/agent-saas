# AGENTS.md - Frontend Agent

<metadata>
<component>Frontend</component>
<tech>Next.js 16, React 19, TypeScript, Tailwind CSS 4, Bun</tech>
<scope>Interface utilisateur, Composants UI, Interactions API</scope>
</metadata>

## 🎨 Identité : Agent Frontend

Je suis l'agent spécialisé dans le **frontend** de la plateforme Agent SaaS.
Mon rôle est de créer une interface **simple, intuitive et accessible** pour des utilisateurs métier non-techniques.

## 🏗️ Architecture

```
frontend/
├── app/
│   ├── layout.tsx          # Layout racine avec metadata
│   ├── page.tsx             # Page principale (dual-mode UI)
│   ├── globals.css          # Styles Tailwind
│   └── components/
│       ├── Chat.tsx             # Interface de chat avec l'IA
│       ├── AgentCard.tsx        # Carte d'affichage d'un agent
│       ├── PromptCard.tsx       # Carte d'affichage d'un prompt
│       ├── MCPToolCard.tsx      # Carte d'outil MCP
│       ├── StatsCard.tsx        # Statistiques dashboard
│       ├── CreateAgentModal.tsx # Modal création agent
│       ├── CreatePromptModal.tsx # Modal création prompt (+ lien MCP)
│       ├── CreateMCPToolModal.tsx # Modal création outil
│       ├── EmployeeWizard.tsx   # Wizard création employé numérique
│       └── WorkflowBuilder.tsx  # Constructeur de workflows simplifié
├── public/                  # Assets statiques
├── package.json             # Dépendances (bun)
├── next.config.ts           # Config Next.js (standalone output)
├── tailwind.config.ts       # Config Tailwind
└── tsconfig.json            # Config TypeScript
```

## 🎯 Principes de Design

### 1. Dual-Mode UI
- **Mode Utilisateur** : Interface simple pour utiliser les agents (chat)
- **Mode Constructeur** : Interface avancée pour configurer (agents, prompts, workflows)

### 2. User-Centric
- Masquer la complexité technique (JSON, cron, variables)
- Utiliser des termes métier compréhensibles
- Boutons et sélecteurs visuels plutôt que formulaires techniques

### 3. Design System
- **Couleurs** : Dark theme (gray-900 base), accents bleu/émeraude/ambre
- **Icônes** : Emojis pour la clarté (pas d'icônes techniques)
- **Feedback** : États loading, success, error bien visibles

## 📡 Communication API

```typescript
const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Pattern standard pour les appels API
const response = await fetch(`${apiUrl}/api/endpoint`);
const data = await response.json();
```

### Endpoints utilisés
| Endpoint | Usage |
|----------|-------|
| `GET /api/agents` | Liste des agents |
| `GET /api/prompts` | Liste des prompts |
| `GET /api/mcp-tools` | Liste des outils MCP |
| `GET /api/workflows` | Liste des workflows |
| `GET /api/business-actions` | Actions métier (Prompt + MCP liés) |
| `GET /api/workflow-task-types` | Types de tâches pour workflow builder |
| `POST /api/chat` | Envoi de message au chat |

## 🔧 Commandes

```bash
# Développement
bun install
bun run dev

# Build production
bun run build

# Lint
bun run lint
```

## ⚠️ Règles Critiques

<rule id="no-api-keys" severity="critical">
JAMAIS de clés API ou secrets dans le code frontend.
Toutes les clés restent côté backend.
</rule>

<rule id="api-proxy" severity="high">
Tous les appels LLM passent par le backend API.
Le frontend ne parle JAMAIS directement à OpenAI/Anthropic.
</rule>

<rule id="user-friendly" severity="high">
Chaque feature doit être compréhensible par un utilisateur non-technique.
Tester mentalement : "Est-ce qu'un chef d'entreprise PME comprend ce bouton ?"
</rule>

## 🎨 Composants Clés

### WorkflowBuilder
Constructeur de workflows **simplifié** avec :
- 3 étapes (Info → Trigger → Blocs)
- Pas de cron brut (presets visuels)
- Actions métier = Prompt + MCP combinés
- Blocs de contrôle simples (Décision, Boucle, Attente, Validation)

### Chat
Interface de conversation avec :
- Sélection d'agent
- Historique de conversation
- Détection de handoff entre agents
- Affichage du scope (Enterprise/Business)

### CreatePromptModal
Création de prompts avec :
- Détection auto des variables `{variable}`
- Liaison optionnelle à un outil MCP → crée une "Action Métier"
- Catégorisation et scope
