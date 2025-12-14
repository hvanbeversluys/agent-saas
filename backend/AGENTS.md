# AGENTS.md - Backend Agent

<metadata>
<component>Backend</component>
<tech>Python 3.11, FastAPI, SQLAlchemy, SQLite, uv</tech>
<scope>API REST, Base de données, Logique métier, Orchestration IA</scope>
</metadata>

## ⚙️ Identité : Agent Backend

Je suis l'agent spécialisé dans le **backend** de la plateforme Agent SaaS.
Mon rôle est de gérer l'**API**, la **base de données**, et l'**orchestration des agents IA**.

## 🏗️ Architecture

```
backend/
├── main.py              # FastAPI app + tous les endpoints
├── database.py          # SQLAlchemy models + seed data
├── requirements.txt     # Dépendances Python
├── Dockerfile           # Image Docker (uv + Python 3.11)
└── agent_saas.db        # Base SQLite (générée au runtime)
```

## 📊 Modèles de Données

### Entités Principales

```
DBAgent          → Employé numérique (nom, prompt système, scope)
DBPrompt         → Template de prompt (variables, lié à MCP optionnel)
DBMCPTool        → Outil externe (email, CRM, docs...)
DBConversation   → Historique des conversations
```

### Entités Workflow/Scheduler

```
DBWorkflow           → Workflow automatisé (trigger, agent associé)
DBWorkflowTask       → Tâche dans un workflow (type, config, ordre)
DBWorkflowExecution  → Instance d'exécution d'un workflow
DBScheduledJob       → Job planifié (cron)
```

### Relations

```
Agent ←→ MCPTool    (Many-to-Many via agent_mcp_tools)
Agent ←→ Prompt     (Many-to-Many via agent_prompts)
Prompt → MCPTool    (Many-to-One, optionnel - crée une "Action Métier")
Workflow → Agent    (Many-to-One)
Workflow → Tasks    (One-to-Many)
```

## 🔌 API Endpoints

### CRUD Standard
| Resource | Endpoints |
|----------|-----------|
| Agents | `GET/POST/PUT/DELETE /api/agents` |
| Prompts | `GET/POST/PUT/DELETE /api/prompts` |
| MCP Tools | `GET/POST/PUT/DELETE /api/mcp-tools` |
| Workflows | `GET/POST/PUT/DELETE /api/workflows` |

### Endpoints Spéciaux
| Endpoint | Description |
|----------|-------------|
| `POST /api/chat` | Chat avec un agent (+ handoff) |
| `GET /api/business-actions` | Actions Métier (Prompt + MCP liés) |
| `GET /api/workflow-task-types` | Metadata pour WorkflowBuilder |
| `POST /api/workflows/{id}/execute` | Exécuter un workflow |
| `GET /api/workflows/{id}/executions` | Historique d'exécution |

## 🧠 Logique Métier

### Concept "Action Métier"
Un prompt lié à un outil MCP devient une "Action Métier" :
- Réutilisable dans les workflows
- Combine instruction IA + action externe
- Ex: "Envoyer email prospection" = Prompt prospection + MCP Email

### Orchestration Chat
1. Reçoit message + agent_id
2. Charge l'agent et son système prompt
3. Analyse si handoff nécessaire vers autre agent
4. Retourne réponse + info handoff éventuel

### Scopes
- **enterprise** : Global à l'entreprise (emails, réunions)
- **business** : Métier spécifique (SEO, prospection, facturation)

## 🔧 Commandes

```bash
# Développement (avec uv)
uv pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Ou avec Docker
docker build -t agent-saas-backend .
docker run -p 8000:8000 agent-saas-backend
```

## ⚠️ Règles Critiques

<rule id="no-frontend-llm" severity="critical">
Le backend est le SEUL à appeler les APIs LLM (OpenAI, Anthropic).
Les clés API ne sortent JAMAIS du backend.
</rule>

<rule id="tenant-isolation" severity="high">
Prévoir l'isolation multi-tenant dès maintenant.
Chaque query doit pouvoir filtrer par tenant_id (à ajouter).
</rule>

<rule id="validation" severity="high">
Valider TOUTES les entrées avec Pydantic.
Ne jamais faire confiance aux données du frontend.
</rule>

## 📝 Patterns de Code

### Endpoint CRUD standard
```python
@app.get("/api/resources", response_model=List[ResourceResponse])
def get_resources(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(DBResource)
    if category:
        query = query.filter(DBResource.category == category)
    return query.all()
```

### Seed Data
Les données de démo sont injectées au startup via `seed_demo_data()`.
Vérifie si la DB est vide avant d'insérer.

## 🚀 Évolutions Prévues

1. **Multi-tenancy** : Ajouter `tenant_id` sur toutes les tables
2. **LangGraph** : Intégrer pour orchestration avancée des agents
3. **MCP SSE** : Connexion aux serveurs MCP distants
4. **Redis** : Cache et queue pour les workflows async
5. **PostgreSQL** : Migration depuis SQLite pour la prod
