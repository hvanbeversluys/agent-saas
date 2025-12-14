# AGENTS.md - Worker Service Agent

<metadata>
<component>Worker</component>
<tech>Python 3.11, LangGraph, ARQ (Redis), LangChain</tech>
<scope>Workflow execution, AI agent orchestration, async tasks</scope>
</metadata>

## 🤖 Identité : Agent Worker

Je suis l'agent spécialisé dans le **worker service** de la plateforme Agent SaaS.
Mon rôle est de gérer l'**exécution des workflows**, l'**orchestration des agents IA**, et les **tâches asynchrones**.

## 🏗️ Architecture

```
worker/
├── AGENTS.md              # Cette documentation
├── Dockerfile             # Image Python + LangGraph
├── requirements.txt       # Dépendances
├── config.py              # Configuration
├── main.py                # Worker principal ARQ
├── graphs/                # LangGraph definitions
│   ├── __init__.py
│   ├── base.py            # Graph de base avec état
│   ├── chat_agent.py      # Agent conversationnel
│   ├── workflow_agent.py  # Exécuteur de workflows
│   └── tool_agent.py      # Agent avec outils MCP
├── tools/                 # Outils MCP (actions)
│   ├── __init__.py
│   ├── base.py            # Tool de base
│   ├── email.py           # Envoi d'emails
│   ├── calendar.py        # Gestion calendrier
│   └── crm.py             # Interactions CRM
├── tasks/                 # Tâches ARQ
│   ├── __init__.py
│   ├── workflow_tasks.py  # Exécution workflows
│   └── scheduled_tasks.py # Jobs planifiés
└── utils/                 # Utilitaires
    ├── __init__.py
    ├── state.py           # Gestion d'état
    └── callbacks.py       # Callbacks LangGraph
```

## 🔧 Technologies

### LangGraph
- **Rôle** : Orchestration des agents IA avec état
- **Features** : Cycles, checkpointing, human-in-the-loop
- **Graphs** : Chat, Workflow, Tool-calling

### ARQ (Async Redis Queue)
- **Rôle** : File d'attente de tâches async
- **Features** : Retry, scheduling, results backend
- **Alternative** : Plus léger que Celery, Python natif async

### Redis
- **Rôle** : Queue broker + state store
- **Features** : Pub/sub pour events, cache pour états

## 🎯 Responsabilités

### 1. Exécution de Workflows
- Déclencher des workflows sur événement/schedule
- Exécuter les étapes séquentiellement ou en parallèle
- Gérer les erreurs et retries
- Logger l'exécution pour audit

### 2. Orchestration Agents IA
- Routing intelligent entre agents
- Tool calling (MCP)
- Gestion de contexte et mémoire
- Human-in-the-loop pour validations

### 3. Tâches Planifiées
- Jobs CRON (emails récurrents, rapports)
- Webhooks entrants
- Polling de sources externes

## 📡 Communication

```
Backend API ──(Redis Queue)──▶ Worker
     │                           │
     │◀──(Redis Pub/Sub)─────────│
     │                           │
     └──(PostgreSQL)─────────────┘
```

### Messages Queue (Backend → Worker)
```json
{
  "task": "execute_workflow",
  "payload": {
    "workflow_id": "wf-123",
    "tenant_id": "tenant-456",
    "trigger": "manual",
    "input_data": {}
  }
}
```

### Events Pub/Sub (Worker → Backend)
```json
{
  "event": "workflow_step_completed",
  "data": {
    "workflow_id": "wf-123",
    "step_id": "step-1",
    "status": "success",
    "output": {}
  }
}
```

## ⚠️ Règles Critiques

<rule id="isolation" severity="critical">
Le worker est ISOLÉ du backend API.
Communication uniquement via Redis (queue + pub/sub).
</rule>

<rule id="idempotency" severity="high">
Toutes les tâches doivent être idempotentes.
Un retry ne doit pas créer de doublons.
</rule>

<rule id="tenant-isolation" severity="high">
Chaque tâche est scopée à un tenant_id.
Jamais de données croisées entre tenants.
</rule>

<rule id="timeout" severity="medium">
Toutes les tâches ont un timeout.
Les LLM calls ont un timeout de 60s max.
</rule>

## 🚀 Commandes

```bash
# Développement
cd worker
pip install -r requirements.txt
arq main.WorkerSettings

# Docker
docker build -t agent-saas-worker .
docker run --env-file .env agent-saas-worker
```

## 📊 Monitoring

- **Logs structurés** : JSON vers stdout
- **Métriques** : Tasks completed, failed, duration
- **Health check** : `/health` endpoint via HTTP
