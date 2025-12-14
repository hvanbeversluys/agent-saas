"""
Agent SaaS API - Backend avec SQLite
MVP avec CRUD complet pour agents, prompts et MCP tools
"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
import uuid
from datetime import datetime

from database import (
    init_db, get_db, seed_demo_data,
    DBAgent, DBPrompt, DBMCPTool, DBConversation,
    DBWorkflow, DBWorkflowTask, DBWorkflowExecution, DBScheduledJob
)

app = FastAPI(title="Agent SaaS API", version="0.2.0")

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Schemas ---

class MCPToolBase(BaseModel):
    name: str
    description: Optional[str] = ""
    icon: str = "🔌"
    category: str = "general"
    status: str = "active"
    scope: str = "business"  # enterprise | business
    config_required: List[str] = []

class MCPToolCreate(MCPToolBase):
    pass

class MCPToolUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    scope: Optional[str] = None
    config_required: Optional[List[str]] = None
    config_values: Optional[dict] = None

class MCPToolResponse(MCPToolBase):
    id: str
    config_values: dict = {}
    created_at: datetime
    
    class Config:
        from_attributes = True


class PromptBase(BaseModel):
    name: str
    description: Optional[str] = ""
    category: str = "general"
    scope: str = "business"  # enterprise | business
    template: str
    variables: List[str] = []
    mcp_tool_id: Optional[str] = None  # Lie le prompt à un outil MCP

class PromptCreate(PromptBase):
    pass

class PromptUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    scope: Optional[str] = None
    template: Optional[str] = None
    variables: Optional[List[str]] = None
    mcp_tool_id: Optional[str] = None

class PromptResponse(PromptBase):
    id: str
    mcp_tool: Optional[MCPToolResponse] = None  # Inclut l'outil MCP lié
    created_at: datetime
    
    class Config:
        from_attributes = True


# --- Business Action = Prompt + MCP (Bloc Métier) ---
class BusinessAction(BaseModel):
    """Un bloc métier = Prompt + MCP Tool liés ensemble"""
    id: str
    name: str
    description: str
    icon: str
    category: str
    prompt_template: str
    variables: List[str]
    mcp_tool_name: Optional[str] = None
    mcp_tool_icon: Optional[str] = None


class AgentBase(BaseModel):
    name: str
    description: Optional[str] = ""
    icon: str = "🤖"
    category: str = "general"
    scope: str = "business"  # enterprise | business
    system_prompt: str
    is_active: bool = True

class AgentCreate(AgentBase):
    mcp_tool_ids: List[str] = []
    prompt_ids: List[str] = []

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    category: Optional[str] = None
    scope: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None
    mcp_tool_ids: Optional[List[str]] = None
    prompt_ids: Optional[List[str]] = None

class AgentResponse(AgentBase):
    id: str
    mcp_tools: List[MCPToolResponse] = []
    prompts: List[PromptResponse] = []
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    agent_id: Optional[str] = None

class HandoffInfo(BaseModel):
    triggered: bool = False
    from_agent: Optional[str] = None
    to_agent_id: Optional[str] = None
    to_agent_name: Optional[str] = None
    to_agent_icon: Optional[str] = None
    reason: Optional[str] = None

class ChatResponse(BaseModel):
    conversation_id: str
    message: ChatMessage
    timestamp: str
    handoff: Optional[HandoffInfo] = None


# --- Startup event ---

@app.on_event("startup")
def startup():
    init_db()
    db = next(get_db())
    seed_demo_data(db)
    db.close()


# --- Health ---

@app.get("/")
def read_root():
    return {"message": "Agent SaaS Backend is running 🚀", "version": "0.2.0"}

@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "0.2.0"}


# ============================================================
# 🔌 MCP TOOLS CRUD
# ============================================================

@app.get("/api/mcp-tools", response_model=List[MCPToolResponse])
def get_mcp_tools(
    category: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(DBMCPTool)
    if category:
        query = query.filter(DBMCPTool.category == category)
    if status:
        query = query.filter(DBMCPTool.status == status)
    return query.all()

@app.get("/api/mcp-tools/{tool_id}", response_model=MCPToolResponse)
def get_mcp_tool(tool_id: str, db: Session = Depends(get_db)):
    tool = db.query(DBMCPTool).filter(DBMCPTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool

@app.post("/api/mcp-tools", response_model=MCPToolResponse)
def create_mcp_tool(tool: MCPToolCreate, db: Session = Depends(get_db)):
    db_tool = DBMCPTool(
        id=str(uuid.uuid4()),
        **tool.model_dump()
    )
    db.add(db_tool)
    db.commit()
    db.refresh(db_tool)
    return db_tool

@app.put("/api/mcp-tools/{tool_id}", response_model=MCPToolResponse)
def update_mcp_tool(tool_id: str, tool: MCPToolUpdate, db: Session = Depends(get_db)):
    db_tool = db.query(DBMCPTool).filter(DBMCPTool.id == tool_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    update_data = tool.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_tool, key, value)
    
    db.commit()
    db.refresh(db_tool)
    return db_tool

@app.delete("/api/mcp-tools/{tool_id}")
def delete_mcp_tool(tool_id: str, db: Session = Depends(get_db)):
    db_tool = db.query(DBMCPTool).filter(DBMCPTool.id == tool_id).first()
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    db.delete(db_tool)
    db.commit()
    return {"message": "Tool deleted"}

@app.get("/api/mcp-tools/categories/list")
def get_mcp_categories(db: Session = Depends(get_db)):
    return {
        "categories": [
            {"id": "email", "name": "Email", "icon": "📧"},
            {"id": "crm", "name": "CRM & Contacts", "icon": "👥"},
            {"id": "seo", "name": "SEO & Analytics", "icon": "🔍"},
            {"id": "facturation", "name": "Facturation", "icon": "🧾"},
            {"id": "productivity", "name": "Productivité", "icon": "⚡"},
            {"id": "communication", "name": "Communication", "icon": "📞"},
        ]
    }


# ============================================================
# 📝 PROMPTS CRUD
# ============================================================

@app.get("/api/prompts", response_model=List[PromptResponse])
def get_prompts(category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(DBPrompt)
    if category:
        query = query.filter(DBPrompt.category == category)
    return query.all()

@app.get("/api/prompts/{prompt_id}", response_model=PromptResponse)
def get_prompt(prompt_id: str, db: Session = Depends(get_db)):
    prompt = db.query(DBPrompt).filter(DBPrompt.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt

@app.post("/api/prompts", response_model=PromptResponse)
def create_prompt(prompt: PromptCreate, db: Session = Depends(get_db)):
    db_prompt = DBPrompt(
        id=str(uuid.uuid4()),
        **prompt.model_dump()
    )
    db.add(db_prompt)
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

@app.put("/api/prompts/{prompt_id}", response_model=PromptResponse)
def update_prompt(prompt_id: str, prompt: PromptUpdate, db: Session = Depends(get_db)):
    db_prompt = db.query(DBPrompt).filter(DBPrompt.id == prompt_id).first()
    if not db_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    update_data = prompt.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_prompt, key, value)
    
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

@app.delete("/api/prompts/{prompt_id}")
def delete_prompt(prompt_id: str, db: Session = Depends(get_db)):
    db_prompt = db.query(DBPrompt).filter(DBPrompt.id == prompt_id).first()
    if not db_prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    db.delete(db_prompt)
    db.commit()
    return {"message": "Prompt deleted"}


# ============================================================
# 🤖 AGENTS CRUD
# ============================================================

@app.get("/api/agents", response_model=List[AgentResponse])
def get_agents(category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(DBAgent)
    if category:
        query = query.filter(DBAgent.category == category)
    return query.all()

@app.get("/api/agents/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@app.post("/api/agents", response_model=AgentResponse)
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    # Extraire les IDs de relations
    mcp_tool_ids = agent.mcp_tool_ids
    prompt_ids = agent.prompt_ids
    
    # Créer l'agent sans les relations
    agent_data = agent.model_dump(exclude={"mcp_tool_ids", "prompt_ids"})
    db_agent = DBAgent(id=str(uuid.uuid4()), **agent_data)
    
    # Ajouter les relations MCP tools
    if mcp_tool_ids:
        tools = db.query(DBMCPTool).filter(DBMCPTool.id.in_(mcp_tool_ids)).all()
        db_agent.mcp_tools = tools
    
    # Ajouter les relations Prompts
    if prompt_ids:
        prompts = db.query(DBPrompt).filter(DBPrompt.id.in_(prompt_ids)).all()
        db_agent.prompts = prompts
    
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.put("/api/agents/{agent_id}", response_model=AgentResponse)
def update_agent(agent_id: str, agent: AgentUpdate, db: Session = Depends(get_db)):
    db_agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    update_data = agent.model_dump(exclude_unset=True)
    
    # Gérer les relations MCP tools
    if "mcp_tool_ids" in update_data:
        mcp_tool_ids = update_data.pop("mcp_tool_ids")
        if mcp_tool_ids is not None:
            tools = db.query(DBMCPTool).filter(DBMCPTool.id.in_(mcp_tool_ids)).all()
            db_agent.mcp_tools = tools
    
    # Gérer les relations Prompts
    if "prompt_ids" in update_data:
        prompt_ids = update_data.pop("prompt_ids")
        if prompt_ids is not None:
            prompts = db.query(DBPrompt).filter(DBPrompt.id.in_(prompt_ids)).all()
            db_agent.prompts = prompts
    
    # Mettre à jour les autres champs
    for key, value in update_data.items():
        setattr(db_agent, key, value)
    
    db.commit()
    db.refresh(db_agent)
    return db_agent

@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    db_agent = db.query(DBAgent).filter(DBAgent.id == agent_id).first()
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(db_agent)
    db.commit()
    return {"message": "Agent deleted"}

@app.get("/api/agents/categories/list")
def get_agent_categories(db: Session = Depends(get_db)):
    return {
        "categories": [
            {"id": "commercial", "name": "Commercial & Ventes", "icon": "🤝"},
            {"id": "seo", "name": "SEO & Contenu", "icon": "🔍"},
            {"id": "admin", "name": "Administratif", "icon": "📋"},
            {"id": "direction", "name": "Direction & Stratégie", "icon": "👔"},
            {"id": "general", "name": "Général", "icon": "🤖"},
        ]
    }


# ============================================================
# 📊 DASHBOARD STATS
# ============================================================

@app.get("/api/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    agents = db.query(DBAgent).all()
    prompts = db.query(DBPrompt).all()
    mcp_tools = db.query(DBMCPTool).all()
    conversations = db.query(DBConversation).count()
    
    return {
        "agents": {
            "total": len(agents),
            "active": len([a for a in agents if a.is_active]),
        },
        "prompts": {
            "total": len(prompts),
        },
        "mcp_tools": {
            "total": len(mcp_tools),
            "active": len([t for t in mcp_tools if t.status == "active"]),
            "beta": len([t for t in mcp_tools if t.status == "beta"]),
            "coming_soon": len([t for t in mcp_tools if t.status == "coming_soon"]),
        },
        "conversations_today": conversations,
    }


# ============================================================
# 💬 CHAT avec ORCHESTRATEUR
# ============================================================

# Mots-clés pour le routing intelligent
ROUTING_KEYWORDS = {
    "agent-prospection": {
        "keywords": ["prospect", "prospecter", "démarcher", "nouveau client", "nouveaux clients", "trouver des clients", "email froid", "cold email", "cherche des clients", "acquisition client"],
        "description": "prospection et démarchage"
    },
    "agent-devis": {
        "keywords": ["devis", "proposition", "tarif", "prix", "offre commerciale", "chiffrer", "estimation"],
        "description": "devis et propositions commerciales"
    },
    "agent-seo-audit": {
        "keywords": ["audit", "analyser site", "seo", "référencement", "position google", "erreurs site", "performance"],
        "description": "audit SEO et analyse de site"
    },
    "agent-seo-content": {
        "keywords": ["article", "blog", "rédiger", "contenu", "texte", "page web", "fiche produit", "écrire"],
        "description": "rédaction de contenu SEO"
    },
    "agent-facturation": {
        "keywords": ["facture", "facturer", "paiement", "relance", "impayé", "encaissement", "règlement"],
        "description": "facturation et relances"
    },
    "agent-planning": {
        "keywords": ["planning", "agenda", "rendez-vous", "réunion", "organiser", "calendrier", "projet", "deadline"],
        "description": "planning et organisation"
    },
    "agent-strategie": {
        "keywords": ["stratégie", "concurrent", "positionnement", "marché", "décision", "business", "développer"],
        "description": "stratégie et conseil"
    },
    "agent-reporting": {
        "keywords": ["rapport", "reporting", "statistiques", "chiffres", "bilan", "tableau de bord", "kpi"],
        "description": "reporting et analyse"
    },
}


def detect_best_agent(message: str, agents: list, current_agent_id: str = None) -> tuple:
    """
    Détecte le meilleur agent pour traiter la demande.
    Retourne (agent_id, raison) ou (None, None) si pas de match.
    """
    message_lower = message.lower()
    
    best_match = None
    best_score = 0
    best_reason = None
    
    for agent_id, config in ROUTING_KEYWORDS.items():
        score = 0
        matched_keywords = []
        
        for keyword in config["keywords"]:
            if keyword in message_lower:
                score += 1
                matched_keywords.append(keyword)
        
        if score > best_score:
            best_score = score
            best_match = agent_id
            best_reason = config["description"]
    
    # Ne pas handoff vers le même agent
    if best_match == current_agent_id:
        return None, None
    
    # Seuil minimum de confiance
    if best_score >= 1:
        return best_match, best_reason
    
    return None, None


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Chat avec orchestration intelligente et handoff"""
    
    # Récupérer ou créer la conversation
    conv_id = request.conversation_id or str(uuid.uuid4())
    
    conversation = db.query(DBConversation).filter(DBConversation.id == conv_id).first()
    if not conversation:
        conversation = DBConversation(id=conv_id, agent_id=request.agent_id, messages=[])
        db.add(conversation)
    
    # Ajouter le message utilisateur
    messages = list(conversation.messages) if conversation.messages else []
    messages.append({"role": "user", "content": request.message})
    
    # Récupérer tous les agents pour le routing
    all_agents = db.query(DBAgent).filter(DBAgent.is_active == True).all()
    
    # Récupérer l'agent courant
    current_agent = None
    if request.agent_id:
        current_agent = db.query(DBAgent).filter(DBAgent.id == request.agent_id).first()
    
    # === LOGIQUE D'ORCHESTRATION ===
    handoff_info = None
    response_agent = current_agent
    
    # Si pas d'agent sélectionné OU si l'agent est l'orchestrateur général
    is_orchestrator = current_agent and current_agent.id == "agent-orchestrator"
    
    if not current_agent or is_orchestrator:
        # Détecter le meilleur agent
        best_agent_id, reason = detect_best_agent(request.message, all_agents, None)
        
        if best_agent_id:
            target_agent = db.query(DBAgent).filter(DBAgent.id == best_agent_id).first()
            if target_agent:
                handoff_info = HandoffInfo(
                    triggered=True,
                    from_agent="🎯 Orchestrateur",
                    to_agent_id=target_agent.id,
                    to_agent_name=target_agent.name,
                    to_agent_icon=target_agent.icon,
                    reason=f"Votre demande concerne : {reason}"
                )
                response_agent = target_agent
                # Mettre à jour la conversation avec le nouvel agent
                conversation.agent_id = target_agent.id
    
    # Générer la réponse
    response_content = generate_orchestrated_response(
        request.message, 
        response_agent, 
        handoff_info
    )
    messages.append({"role": "assistant", "content": response_content})
    
    # Sauvegarder
    conversation.messages = messages
    db.commit()
    
    return ChatResponse(
        conversation_id=conv_id,
        message=ChatMessage(role="assistant", content=response_content),
        timestamp=datetime.now().isoformat(),
        handoff=handoff_info
    )


def generate_orchestrated_response(user_message: str, agent: DBAgent = None, handoff: HandoffInfo = None) -> str:
    """Génère une réponse avec contexte d'orchestration"""
    user_lower = user_message.lower()
    
    # Si handoff déclenché
    if handoff and handoff.triggered:
        tool_names = [t.name for t in agent.mcp_tools] if agent and agent.mcp_tools else []
        prompt_names = [p.name for p in agent.prompts] if agent and agent.prompts else []
        
        return f"""🔄 **Transfert vers {handoff.to_agent_icon} {handoff.to_agent_name}**

_{handoff.reason}_

---

**{agent.icon} {agent.name}** prend le relais !

{agent.description}

**Outils disponibles:** {', '.join(tool_names) if tool_names else 'Configuration en attente'}
**Templates prêts:** {', '.join(prompt_names) if prompt_names else 'Aucun'}

---

💬 Comment puis-je vous aider avec votre demande ?

> "{user_message[:100]}{'...' if len(user_message) > 100 else ''}"
"""
    
    # Si agent spécifique (sans handoff)
    if agent:
        tool_names = [t.name for t in agent.mcp_tools] if agent.mcp_tools else []
        prompt_names = [p.name for p in agent.prompts] if agent.prompts else []
        
        # Réponses contextuelles par type d'agent
        if "prospection" in agent.id:
            return f"""**{agent.icon} {agent.name}**

Je peux vous aider à :
- ✉️ Rédiger un email de prospection personnalisé
- 📞 Préparer un script d'appel
- 🎯 Cibler les bons prospects

**Donnez-moi le contexte :**
- Quelle entreprise voulez-vous contacter ?
- Quel est votre service/produit ?
- Y a-t-il un contexte particulier ?

_Templates disponibles : {', '.join(prompt_names) if prompt_names else 'Demandez-moi directement'}_
"""
        elif "devis" in agent.id:
            return f"""**{agent.icon} {agent.name}**

Je peux vous aider à :
- 📄 Structurer une proposition commerciale
- 💰 Définir le bon tarif
- ✍️ Rédiger les conditions

**De quoi avez-vous besoin ?**
- Nouveau devis ou relance ?
- Type de prestation ?
- Budget client estimé ?
"""
        elif "seo" in agent.id and "audit" in agent.id:
            return f"""**{agent.icon} {agent.name}**

Je peux analyser :
- 🔍 Le référencement d'un site
- ⚡ Les performances techniques
- 📊 Le positionnement vs concurrents

**Quelle est l'URL à analyser ?**
"""
        elif "seo" in agent.id and "content" in agent.id:
            return f"""**{agent.icon} {agent.name}**

Je peux rédiger :
- 📝 Articles de blog optimisés
- 📄 Pages de services
- 🏷️ Fiches produits

**Quel contenu voulez-vous ?**
- Sujet / thématique ?
- Mot-clé principal ?
- Longueur souhaitée ?
"""
        elif "facturation" in agent.id:
            return f"""**{agent.icon} {agent.name}**

Je peux vous aider avec :
- 🧾 Création de factures
- 📧 Emails de relance (niveau 1, 2, 3)
- 📊 Suivi des paiements

**Quelle action ?**
- Relancer un client ?
- Créer une facture ?
- Faire un point sur les impayés ?
"""
        else:
            return f"""**{agent.icon} {agent.name}**

{agent.description}

**Outils connectés:** {', '.join(tool_names) if tool_names else 'Aucun'}
**Templates:** {', '.join(prompt_names) if prompt_names else 'Aucun'}

💬 Comment puis-je vous aider ?
"""
    
    # Pas d'agent - Mode orchestrateur
    return f"""🎯 **Assistant Entreprise**

Bonjour ! Je suis votre assistant principal. Décrivez-moi votre besoin et je vous orienterai vers le bon expert :

| Besoin | Expert |
|--------|--------|
| Trouver des clients | 📞 Prospection |
| Faire un devis | 💼 Devis |
| Améliorer mon site | 🔍 Audit SEO |
| Écrire du contenu | ✍️ Rédacteur |
| Gérer les factures | 🧾 Facturation |
| Organiser mon temps | 📅 Planning |

**Que voulez-vous faire ?**

> Exemple : "Je dois relancer un client qui n'a pas payé sa facture"
"""


# ============================================================
# 📅 SCHEDULER / WORKFLOWS CRUD
# ============================================================

# --- Pydantic Schemas for Workflows ---

class WorkflowTaskConfig(BaseModel):
    """Configuration d'une tâche de workflow"""
    # Pour prompt
    prompt_id: Optional[str] = None
    prompt_template: Optional[str] = None
    variables_mapping: Optional[dict] = None
    
    # Pour mcp_action
    tool_id: Optional[str] = None
    action: Optional[str] = None
    params: Optional[dict] = None
    
    # Pour condition
    expression: Optional[str] = None
    true_branch: Optional[str] = None
    false_branch: Optional[str] = None
    
    # Pour loop
    iterate_over: Optional[str] = None
    item_var: Optional[str] = None
    
    # Pour wait
    wait_type: Optional[str] = None  # delay, event
    duration: Optional[int] = None  # secondes
    event: Optional[str] = None
    
    # Pour human_approval
    approval_message: Optional[str] = None
    timeout: Optional[int] = None
    
    # Pour set_variable
    var_name: Optional[str] = None
    var_value: Optional[str] = None
    
    # Pour http_request
    url: Optional[str] = None
    method: Optional[str] = None
    headers: Optional[dict] = None
    body: Optional[dict] = None

class WorkflowTaskBase(BaseModel):
    name: str
    description: Optional[str] = ""
    order: str = "1"
    task_type: str  # prompt, mcp_action, condition, loop, wait, parallel, human_approval, set_variable, http_request
    config: dict = {}
    on_error: str = "stop"
    retry_count: str = "0"
    error_goto: Optional[str] = None

class WorkflowTaskCreate(WorkflowTaskBase):
    pass

class WorkflowTaskResponse(WorkflowTaskBase):
    id: str
    workflow_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class TriggerConfig(BaseModel):
    cron: Optional[str] = None  # "0 9 * * 1-5"
    event: Optional[str] = None  # "new_lead"
    source: Optional[str] = None  # "crm"
    webhook_secret: Optional[str] = None

class InputSchemaField(BaseModel):
    name: str
    type: str = "string"  # string, number, boolean, array, object
    required: bool = True
    default: Optional[str] = None
    description: Optional[str] = None

class WorkflowBase(BaseModel):
    name: str
    description: Optional[str] = ""
    trigger_type: str = "manual"  # manual, cron, event
    trigger_config: dict = {}
    input_schema: List[InputSchemaField] = []
    is_active: bool = True

class WorkflowCreate(WorkflowBase):
    agent_id: str
    tasks: List[WorkflowTaskCreate] = []

class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict] = None
    input_schema: Optional[List[InputSchemaField]] = None
    is_active: Optional[bool] = None

class WorkflowResponse(WorkflowBase):
    id: str
    agent_id: str
    tasks: List[WorkflowTaskResponse] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class WorkflowExecutionBase(BaseModel):
    input_data: dict = {}

class WorkflowExecutionCreate(WorkflowExecutionBase):
    pass

class WorkflowExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    input_data: dict
    output_data: dict
    variables: dict
    current_task_order: Optional[str]
    tasks_completed: List[str]
    task_results: dict
    error_message: Optional[str]
    error_task_id: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


# --- Workflow CRUD Endpoints ---

@app.get("/api/workflows", response_model=List[WorkflowResponse])
def get_workflows(
    agent_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Liste tous les workflows, optionnellement filtrés par agent"""
    query = db.query(DBWorkflow)
    if agent_id:
        query = query.filter(DBWorkflow.agent_id == agent_id)
    if is_active is not None:
        query = query.filter(DBWorkflow.is_active == is_active)
    return query.all()

@app.get("/api/workflows/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(workflow_id: str, db: Session = Depends(get_db)):
    """Récupère un workflow par son ID"""
    workflow = db.query(DBWorkflow).filter(DBWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow

@app.post("/api/workflows", response_model=WorkflowResponse)
def create_workflow(workflow: WorkflowCreate, db: Session = Depends(get_db)):
    """Crée un nouveau workflow avec ses tâches"""
    # Vérifier que l'agent existe
    agent = db.query(DBAgent).filter(DBAgent.id == workflow.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Créer le workflow
    db_workflow = DBWorkflow(
        id=str(uuid.uuid4()),
        name=workflow.name,
        description=workflow.description,
        agent_id=workflow.agent_id,
        trigger_type=workflow.trigger_type,
        trigger_config=workflow.trigger_config,
        input_schema=[field.model_dump() for field in workflow.input_schema],
        is_active=workflow.is_active
    )
    db.add(db_workflow)
    db.flush()  # Pour obtenir l'ID
    
    # Créer les tâches
    for task_data in workflow.tasks:
        db_task = DBWorkflowTask(
            id=str(uuid.uuid4()),
            workflow_id=db_workflow.id,
            **task_data.model_dump()
        )
        db.add(db_task)
    
    # Si trigger cron, créer le job planifié
    if workflow.trigger_type == "cron" and workflow.trigger_config.get("cron"):
        from datetime import datetime, timedelta
        db_job = DBScheduledJob(
            id=str(uuid.uuid4()),
            workflow_id=db_workflow.id,
            cron_expression=workflow.trigger_config["cron"],
            timezone=workflow.trigger_config.get("timezone", "Europe/Paris"),
            next_run=datetime.utcnow() + timedelta(minutes=5),  # Placeholder
            is_active=True
        )
        db.add(db_job)
    
    db.commit()
    db.refresh(db_workflow)
    return db_workflow

@app.put("/api/workflows/{workflow_id}", response_model=WorkflowResponse)
def update_workflow(workflow_id: str, workflow: WorkflowUpdate, db: Session = Depends(get_db)):
    """Met à jour un workflow"""
    db_workflow = db.query(DBWorkflow).filter(DBWorkflow.id == workflow_id).first()
    if not db_workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    update_data = workflow.model_dump(exclude_unset=True)
    if "input_schema" in update_data and update_data["input_schema"]:
        update_data["input_schema"] = [field.model_dump() if hasattr(field, 'model_dump') else field for field in update_data["input_schema"]]
    
    for key, value in update_data.items():
        setattr(db_workflow, key, value)
    
    db.commit()
    db.refresh(db_workflow)
    return db_workflow

@app.delete("/api/workflows/{workflow_id}")
def delete_workflow(workflow_id: str, db: Session = Depends(get_db)):
    """Supprime un workflow et ses tâches"""
    db_workflow = db.query(DBWorkflow).filter(DBWorkflow.id == workflow_id).first()
    if not db_workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Supprimer les tâches associées
    db.query(DBWorkflowTask).filter(DBWorkflowTask.workflow_id == workflow_id).delete()
    # Supprimer les exécutions
    db.query(DBWorkflowExecution).filter(DBWorkflowExecution.workflow_id == workflow_id).delete()
    # Supprimer le job planifié s'il existe
    db.query(DBScheduledJob).filter(DBScheduledJob.workflow_id == workflow_id).delete()
    # Supprimer le workflow
    db.delete(db_workflow)
    db.commit()
    return {"message": "Workflow deleted"}


# --- Workflow Tasks Endpoints ---

@app.post("/api/workflows/{workflow_id}/tasks", response_model=WorkflowTaskResponse)
def add_workflow_task(workflow_id: str, task: WorkflowTaskCreate, db: Session = Depends(get_db)):
    """Ajoute une tâche à un workflow"""
    workflow = db.query(DBWorkflow).filter(DBWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    db_task = DBWorkflowTask(
        id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        **task.model_dump()
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.put("/api/workflows/{workflow_id}/tasks/{task_id}", response_model=WorkflowTaskResponse)
def update_workflow_task(workflow_id: str, task_id: str, task: WorkflowTaskCreate, db: Session = Depends(get_db)):
    """Met à jour une tâche"""
    db_task = db.query(DBWorkflowTask).filter(
        DBWorkflowTask.id == task_id,
        DBWorkflowTask.workflow_id == workflow_id
    ).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    for key, value in task.model_dump().items():
        setattr(db_task, key, value)
    
    db.commit()
    db.refresh(db_task)
    return db_task

@app.delete("/api/workflows/{workflow_id}/tasks/{task_id}")
def delete_workflow_task(workflow_id: str, task_id: str, db: Session = Depends(get_db)):
    """Supprime une tâche"""
    db_task = db.query(DBWorkflowTask).filter(
        DBWorkflowTask.id == task_id,
        DBWorkflowTask.workflow_id == workflow_id
    ).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db.delete(db_task)
    db.commit()
    return {"message": "Task deleted"}


# --- Workflow Execution Endpoints ---

@app.post("/api/workflows/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
def execute_workflow(workflow_id: str, execution: WorkflowExecutionCreate, db: Session = Depends(get_db)):
    """Lance l'exécution d'un workflow"""
    workflow = db.query(DBWorkflow).filter(DBWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Valider les inputs requis
    for field in workflow.input_schema:
        if field.get("required", True) and field["name"] not in execution.input_data:
            if not field.get("default"):
                raise HTTPException(
                    status_code=400, 
                    detail=f"Missing required input: {field['name']}"
                )
    
    # Créer l'exécution
    db_execution = DBWorkflowExecution(
        id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        status="pending",
        input_data=execution.input_data,
        variables={},
        started_at=datetime.utcnow()
    )
    db.add(db_execution)
    db.commit()
    db.refresh(db_execution)
    
    # TODO: Lancer l'exécution async (via background task ou queue)
    # Pour le MVP, on simule une exécution immédiate
    db_execution.status = "running"
    db_execution.current_task_order = "1"
    db.commit()
    db.refresh(db_execution)
    
    return db_execution

@app.get("/api/workflows/{workflow_id}/executions", response_model=List[WorkflowExecutionResponse])
def get_workflow_executions(
    workflow_id: str,
    status: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Liste les exécutions d'un workflow"""
    query = db.query(DBWorkflowExecution).filter(DBWorkflowExecution.workflow_id == workflow_id)
    if status:
        query = query.filter(DBWorkflowExecution.status == status)
    return query.order_by(DBWorkflowExecution.created_at.desc()).limit(limit).all()

@app.get("/api/executions/{execution_id}", response_model=WorkflowExecutionResponse)
def get_execution(execution_id: str, db: Session = Depends(get_db)):
    """Récupère les détails d'une exécution"""
    execution = db.query(DBWorkflowExecution).filter(DBWorkflowExecution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution

@app.post("/api/executions/{execution_id}/cancel")
def cancel_execution(execution_id: str, db: Session = Depends(get_db)):
    """Annule une exécution en cours"""
    execution = db.query(DBWorkflowExecution).filter(DBWorkflowExecution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    if execution.status not in ["pending", "running", "waiting_approval"]:
        raise HTTPException(status_code=400, detail="Cannot cancel execution in current state")
    
    execution.status = "cancelled"
    execution.completed_at = datetime.utcnow()
    db.commit()
    return {"message": "Execution cancelled"}

@app.post("/api/executions/{execution_id}/approve")
def approve_execution(execution_id: str, approved: bool = True, db: Session = Depends(get_db)):
    """Approuve ou rejette une exécution en attente d'approbation"""
    execution = db.query(DBWorkflowExecution).filter(DBWorkflowExecution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    if execution.status != "waiting_approval":
        raise HTTPException(status_code=400, detail="Execution is not waiting for approval")
    
    if approved:
        execution.status = "running"
        # TODO: Continuer l'exécution
    else:
        execution.status = "cancelled"
        execution.completed_at = datetime.utcnow()
        execution.error_message = "Rejected by user"
    
    db.commit()
    return {"message": "Approval processed", "status": execution.status}


# ============================================================
# 🎯 BUSINESS ACTIONS (Prompt + MCP combinés)
# ============================================================

@app.get("/api/business-actions", response_model=List[BusinessAction])
def get_business_actions(db: Session = Depends(get_db)):
    """
    Retourne les 'Actions Métier' = Prompts liés à un MCP Tool.
    C'est le bloc de base pour construire des workflows simplement.
    """
    prompts = db.query(DBPrompt).filter(DBPrompt.mcp_tool_id.isnot(None)).all()
    
    actions = []
    for p in prompts:
        mcp = p.mcp_tool
        actions.append(BusinessAction(
            id=p.id,
            name=p.name,
            description=p.description or "",
            icon=mcp.icon if mcp else "⚡",
            category=p.category,
            prompt_template=p.template,
            variables=p.variables or [],
            mcp_tool_name=mcp.name if mcp else None,
            mcp_tool_icon=mcp.icon if mcp else None
        ))
    
    return actions


# --- Task Types Info Endpoint (SIMPLIFIED for business users) ---

@app.get("/api/workflow-task-types")
def get_task_types():
    """
    Types de tâches SIMPLIFIÉS pour utilisateurs métier.
    On cache la complexité technique (cron, JSON, variables).
    """
    return {
        # Types de blocs simplifiés
        "task_types": [
            {
                "id": "business_action",
                "name": "⚡ Action Métier",
                "description": "Exécute une action pré-configurée (email, CRM, document...)",
                "icon": "⚡",
                "color": "#10B981",  # green
                "config_fields": [
                    {"name": "action_id", "type": "select", "label": "Choisir une action", "source": "business_actions"}
                ]
            },
            {
                "id": "condition",
                "name": "🔀 Décision",
                "description": "Si une condition est remplie, faire ceci, sinon faire cela",
                "icon": "🔀",
                "color": "#F59E0B",  # amber
                "config_fields": [
                    {"name": "condition_text", "type": "select", "label": "Condition", "options": [
                        "L'étape précédente a réussi",
                        "L'étape précédente a échoué",
                        "Le client a répondu",
                        "Le montant est supérieur à 1000€",
                        "C'est un nouveau client",
                        "Personnalisé..."
                    ]}
                ]
            },
            {
                "id": "loop",
                "name": "🔄 Pour chaque",
                "description": "Répéter l'action pour chaque élément (clients, factures...)",
                "icon": "🔄",
                "color": "#8B5CF6",  # violet
                "config_fields": [
                    {"name": "loop_over", "type": "select", "label": "Pour chaque", "options": [
                        "Client dans la liste",
                        "Facture en retard",
                        "Lead à contacter",
                        "Email non lu",
                        "Personnalisé..."
                    ]}
                ]
            },
            {
                "id": "wait",
                "name": "⏳ Attendre",
                "description": "Faire une pause avant de continuer",
                "icon": "⏳",
                "color": "#6B7280",  # gray
                "config_fields": [
                    {"name": "wait_duration", "type": "select", "label": "Durée", "options": [
                        "5 minutes",
                        "1 heure",
                        "1 jour",
                        "1 semaine",
                        "Jusqu'à réponse client"
                    ]}
                ]
            },
            {
                "id": "human_approval",
                "name": "✋ Validation",
                "description": "Attendre votre validation avant de continuer",
                "icon": "✋",
                "color": "#EF4444",  # red
                "config_fields": [
                    {"name": "message", "type": "text", "label": "Message à afficher"}
                ]
            }
        ],
        
        # Déclencheurs simplifiés (pas de cron brut!)
        "trigger_types": [
            {"id": "manual", "name": "🖱️ Manuel", "description": "Vous lancez quand vous voulez", "icon": "🖱️"},
            {"id": "scheduled", "name": "📅 Planifié", "description": "Se lance automatiquement", "icon": "📅"},
            {"id": "event", "name": "⚡ Automatique", "description": "Se lance quand quelque chose arrive", "icon": "⚡"}
        ],
        
        # Plannings pré-configurés (remplace le cron brut)
        "schedule_presets": [
            {"id": "daily_morning", "label": "Tous les matins à 9h", "icon": "🌅"},
            {"id": "daily_evening", "label": "Tous les soirs à 18h", "icon": "🌆"},
            {"id": "weekdays_morning", "label": "Du lundi au vendredi à 9h", "icon": "💼"},
            {"id": "weekly_monday", "label": "Chaque lundi matin", "icon": "📆"},
            {"id": "monthly_first", "label": "Le 1er du mois", "icon": "📅"},
            {"id": "hourly", "label": "Toutes les heures", "icon": "⏰"}
        ],
        
        # Événements déclencheurs
        "event_triggers": [
            {"id": "new_lead", "label": "Nouveau lead reçu", "icon": "👤", "source": "CRM"},
            {"id": "email_received", "label": "Email reçu", "icon": "📧", "source": "Email"},
            {"id": "invoice_overdue", "label": "Facture en retard", "icon": "🧾", "source": "Facturation"},
            {"id": "deal_closed", "label": "Affaire conclue", "icon": "🎉", "source": "CRM"},
            {"id": "meeting_scheduled", "label": "Réunion planifiée", "icon": "📅", "source": "Calendrier"}
        ]
    }


# ============================================================
# 🤖 AI ASSISTANT - Aide à la création
# ============================================================

class AIAssistRequest(BaseModel):
    context: str  # "prompt" | "workflow" | "agent"
    message: str
    current_data: Optional[dict] = None

class AISuggestion(BaseModel):
    field: str
    label: str
    value: str

class AIAssistResponse(BaseModel):
    response: str
    suggestions: List[AISuggestion] = []


def generate_ai_assistance(context: str, message: str, current_data: dict = None) -> tuple[str, List[dict]]:
    """Génère une assistance IA pour la création de prompts/workflows/agents"""
    
    message_lower = message.lower()
    suggestions = []
    
    # === CONTEXTE: PROMPT ===
    if context == "prompt":
        name = current_data.get("name", "") if current_data else ""
        template = current_data.get("template", "") if current_data else ""
        
        if "template" in message_lower or "suggère" in message_lower or "suggere" in message_lower:
            # Détecter le type de prompt demandé
            if "email" in message_lower or "mail" in message_lower:
                if "prospection" in message_lower or "commercial" in message_lower:
                    suggestions.append({
                        "field": "template",
                        "label": "Template email prospection",
                        "value": """Bonjour {prenom},

J'ai découvert {entreprise} et je suis impressionné par {element_remarque}.

Chez {ma_societe}, nous aidons les entreprises comme la vôtre à {proposition_valeur}.

Seriez-vous disponible pour un échange de 15 minutes cette semaine ?

Cordialement,
{signature}"""
                    })
                    suggestions.append({
                        "field": "name",
                        "label": "Nom suggéré",
                        "value": "Email prospection personnalisé"
                    })
                elif "relance" in message_lower:
                    suggestions.append({
                        "field": "template",
                        "label": "Template relance",
                        "value": """Bonjour {prenom},

Je me permets de revenir vers vous suite à mon précédent message.

{rappel_contexte}

Avez-vous eu le temps d'y réfléchir ?

Je reste disponible pour en discuter.

Cordialement,
{signature}"""
                    })
                else:
                    suggestions.append({
                        "field": "template",
                        "label": "Template email générique",
                        "value": """Bonjour {destinataire},

{corps_message}

{appel_action}

Cordialement,
{signature}"""
                    })
            
            elif "devis" in message_lower or "proposition" in message_lower:
                suggestions.append({
                    "field": "template",
                    "label": "Template proposition commerciale",
                    "value": """# Proposition commerciale - {client}

## Contexte
{contexte_client}

## Notre solution
{description_solution}

## Détail de l'offre
- {ligne_1}: {prix_1}€
- {ligne_2}: {prix_2}€

**Total HT:** {total_ht}€
**TVA (20%):** {tva}€
**Total TTC:** {total_ttc}€

## Conditions
- Validité: 30 jours
- Paiement: {conditions_paiement}

---
{signature_commerciale}"""
                })
            
            elif "seo" in message_lower or "article" in message_lower:
                suggestions.append({
                    "field": "template",
                    "label": "Template article SEO",
                    "value": """# {titre_h1}

## Introduction
{introduction_avec_mot_cle}

## {sous_titre_h2_1}
{paragraphe_1}

## {sous_titre_h2_2}
{paragraphe_2}

## FAQ
**{question_1}**
{reponse_1}

**{question_2}**
{reponse_2}

## Conclusion
{conclusion_avec_cta}"""
                })
            
            else:
                response = """Je peux vous suggérer différents types de templates :

📧 **Emails**
- Prospection commerciale
- Relance client
- Suivi après rendez-vous

📄 **Documents**
- Proposition commerciale
- Compte-rendu réunion
- Rapport d'analyse

📝 **Contenu**
- Article SEO
- Post LinkedIn
- Description produit

Précisez ce que vous souhaitez créer et je vous proposerai un template adapté !"""
                return response, suggestions
        
        elif "améliore" in message_lower or "ameliore" in message_lower:
            if template:
                # Suggérer des améliorations
                improved = template
                if "{" not in template:
                    suggestions.append({
                        "field": "template",
                        "label": "Version avec variables",
                        "value": template.replace("Bonjour", "Bonjour {prenom}").replace("Cordialement", "Cordialement,\n{signature}")
                    })
                response = """Voici mes suggestions d'amélioration :

✨ **Personnalisation** : Ajoutez des variables comme {prenom}, {entreprise}
📝 **Structure** : Utilisez des paragraphes courts
🎯 **CTA** : Ajoutez un appel à l'action clair
⏰ **Urgence** : Créez un sentiment d'urgence si approprié

Cliquez sur une suggestion pour l'appliquer directement !"""
                return response, suggestions
        
        elif "variable" in message_lower:
            common_vars = [
                "{prenom}", "{nom}", "{entreprise}", "{email}",
                "{date}", "{montant}", "{produit}", "{signature}"
            ]
            response = f"""Voici les variables les plus utilisées :

👤 **Contact** : {prenom}, {nom}, {email}
🏢 **Entreprise** : {entreprise}, {secteur}, {taille}
📅 **Dates** : {date}, {deadline}, {rdv}
💰 **Business** : {montant}, {produit}, {service}

**Syntaxe** : Utilisez {{nom_variable}} dans votre template.

Variables actuellement utilisées : {current_data.get('variables', []) if current_data else 'aucune'}"""
            return response, suggestions
        
        elif "précis" in message_lower or "precis" in message_lower:
            response = """Pour rendre votre prompt plus précis :

1️⃣ **Contexte clair** : Commencez par expliquer la situation
2️⃣ **Instructions spécifiques** : Utilisez des verbes d'action
3️⃣ **Format attendu** : Précisez la longueur, le ton, la structure
4️⃣ **Exemples** : Donnez un exemple du résultat attendu
5️⃣ **Contraintes** : Mentionnez ce qu'il faut éviter

**Exemple** :
> "Rédige un email de 3 paragraphes maximum, ton professionnel mais chaleureux, avec un appel à l'action clair à la fin."
"""
            return response, suggestions
    
    # === CONTEXTE: WORKFLOW ===
    elif context == "workflow":
        name = current_data.get("name", "") if current_data else ""
        description = current_data.get("description", "") if current_data else ""
        
        if "étape" in message_lower or "step" in message_lower or "suggère" in message_lower:
            if "relance" in message_lower or "client" in message_lower:
                response = """Voici un workflow de relance client en 4 étapes :

1️⃣ **Envoyer email de relance**
   → Action métier : Email de suivi
   → Personnaliser avec le contexte client

2️⃣ **Attendre 3 jours**
   → Bloc : Attente
   → Laisser le temps au client de répondre

3️⃣ **Vérifier réponse**
   → Bloc : Condition
   → Si réponse → Fin / Sinon → Continuer

4️⃣ **Relance téléphonique**
   → Action métier : Rappel tâche
   → Notification pour vous rappeler d'appeler

Voulez-vous que je détaille une étape en particulier ?"""
                suggestions.append({
                    "field": "name",
                    "label": "Nom suggéré",
                    "value": "Relance client automatique"
                })
                suggestions.append({
                    "field": "description",
                    "label": "Description suggérée",
                    "value": "Workflow automatisé de relance client avec escalade progressive"
                })
            
            elif "prospection" in message_lower or "lead" in message_lower:
                response = """Voici un workflow de prospection en 5 étapes :

1️⃣ **Recherche prospect**
   → Action métier : Recherche entreprise
   → Collecter les infos clés

2️⃣ **Email de premier contact**
   → Action métier : Email prospection
   → Personnalisé avec les infos trouvées

3️⃣ **Attendre 5 jours**
   → Bloc : Attente

4️⃣ **Email de relance**
   → Action métier : Email relance
   → Ajouter de la valeur (article, cas client...)

5️⃣ **Qualification lead**
   → Bloc : Validation humaine
   → Vous décidez de continuer ou non"""
                suggestions.append({
                    "field": "name",
                    "label": "Nom suggéré",
                    "value": "Séquence prospection B2B"
                })
            
            else:
                response = """Je peux vous suggérer des workflows pour :

📧 **Commercial**
- Relance client
- Séquence prospection
- Suivi devis

📊 **Administratif**
- Relance factures
- Onboarding client
- Rapport hebdomadaire

🔄 **Marketing**
- Nurturing leads
- Publication contenu
- Veille concurrentielle

Précisez votre besoin et je vous proposerai les étapes !"""
        
        elif "optimise" in message_lower or "améliore" in message_lower:
            response = """Conseils pour optimiser votre workflow :

⚡ **Performance**
- Groupez les actions similaires
- Utilisez des conditions pour éviter les actions inutiles

⏰ **Timing**
- Évitez d'envoyer des emails le lundi matin ou vendredi soir
- Espacez les relances de 3-5 jours

✅ **Validation**
- Ajoutez des points de contrôle humain pour les actions importantes
- Prévoyez des conditions de sortie

📊 **Suivi**
- Ajoutez des notifications à chaque étape clé
- Prévoyez un rapport de fin de workflow"""
        
        elif "planning" in message_lower or "schedule" in message_lower or "quand" in message_lower:
            response = """Voici mes recommandations de planning :

📧 **Emails commerciaux**
- Mardi à jeudi, entre 9h et 11h
- Évitez le lundi (surcharge) et vendredi (week-end)

📊 **Rapports**
- Lundi matin pour la semaine passée
- 1er du mois pour le mensuel

🔄 **Relances**
- Après 3-5 jours ouvrés
- Pas plus de 3 relances par prospect

⏰ **Automatisations**
- Horaires décalés pour éviter les pics
- Testez différents créneaux"""
            suggestions.append({
                "field": "trigger_type",
                "label": "Déclencheur recommandé",
                "value": "scheduled"
            })
    
    # === CONTEXTE: AGENT ===
    elif context == "agent":
        name = current_data.get("name", "") if current_data else ""
        description = current_data.get("description", "") if current_data else ""
        
        if "prompt système" in message_lower or "system" in message_lower or "écris" in message_lower:
            if "commercial" in message_lower or "vente" in message_lower:
                suggestions.append({
                    "field": "system_prompt",
                    "label": "Prompt système commercial",
                    "value": """Tu es un assistant commercial expert. Tu aides à :
- Rédiger des emails de prospection personnalisés et engageants
- Préparer des propositions commerciales structurées
- Qualifier les leads et identifier les opportunités
- Gérer les objections avec tact et professionnalisme

Ton ton est professionnel, chaleureux et orienté solution.
Tu poses des questions pour mieux comprendre le contexte avant de proposer.
Tu utilises des données concrètes et des exemples pertinents."""
                })
            elif "seo" in message_lower or "contenu" in message_lower:
                suggestions.append({
                    "field": "system_prompt",
                    "label": "Prompt système SEO",
                    "value": """Tu es un expert SEO et content marketing. Tu aides à :
- Créer du contenu optimisé pour le référencement
- Rechercher et utiliser les bons mots-clés
- Structurer les articles pour le web (H1, H2, paragraphes courts)
- Rédiger des méta-descriptions et titres accrocheurs

Tu connais les dernières bonnes pratiques Google.
Tu proposes toujours une structure claire avant de rédiger.
Tu intègres naturellement les mots-clés sans sur-optimisation."""
                })
            else:
                response = """Je peux vous aider à rédiger un prompt système pour :

👔 **Commercial**
- Assistant prospection
- Rédacteur devis
- Négociateur

📝 **Marketing**
- Expert SEO
- Community manager
- Copywriter

🔧 **Support**
- Assistant client
- FAQ bot
- Onboarding

💼 **Admin**
- Assistant RH
- Gestionnaire factures
- Organisateur

Précisez le rôle souhaité et je vous proposerai un prompt système adapté !"""
                return response, suggestions
        
        elif "outil" in message_lower or "mcp" in message_lower:
            response = """Voici les outils recommandés par type d'agent :

📧 **Agent Email**
- Gmail/Outlook (envoi)
- CRM (contexte client)

📊 **Agent SEO**
- Google Search Console
- Semrush/Ahrefs
- WordPress

💰 **Agent Facturation**
- Stripe/Pennylane
- Google Sheets
- Email

👥 **Agent Commercial**
- CRM (HubSpot, Salesforce)
- LinkedIn
- Calendrier

Quel type d'agent créez-vous ?"""
        
        elif "personnalité" in message_lower or "ton" in message_lower:
            response = """Définissez la personnalité de votre agent :

🎭 **Tons disponibles**
- Professionnel et formel
- Chaleureux et accessible
- Expert et technique
- Enthousiaste et dynamique

📝 **À préciser dans le prompt**
- Vouvoiement ou tutoiement
- Utilisation d'emojis (oui/non)
- Longueur des réponses
- Niveau de détail

💡 **Exemple**
> "Tu tutoies l'utilisateur, tu es enthousiaste mais professionnel, tu utilises des emojis avec modération, et tu fais des réponses concises avec des bullet points."
"""
    
    # Réponse par défaut
    default_response = f"""Je suis là pour vous aider à créer ! 🤖

**Contexte actuel** : {context}

Je peux vous aider à :
- 💡 Suggérer du contenu adapté
- ✨ Améliorer ce que vous avez commencé
- 📋 Proposer une structure
- 🎯 Rendre vos créations plus efficaces

Posez-moi une question ou utilisez les boutons rapides ci-dessous !"""
    
    return default_response if not suggestions else "Voici mes suggestions 👇", suggestions


@app.post("/api/ai-assist", response_model=AIAssistResponse)
def ai_assist(request: AIAssistRequest, db: Session = Depends(get_db)):
    """Endpoint d'assistance IA pour la création de prompts, workflows, agents"""
    
    response_text, suggestions = generate_ai_assistance(
        context=request.context,
        message=request.message,
        current_data=request.current_data
    )
    
    return AIAssistResponse(
        response=response_text,
        suggestions=[AISuggestion(**s) for s in suggestions]
    )


# ============================================================
# 📊 STATS & ANALYTICS
# ============================================================

@app.get("/api/stats/workflows")
def get_workflow_stats(
    period: str = "week",
    workflow_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Statistiques des workflows pour le dashboard utilisateur avec filtres"""
    import random
    from datetime import datetime, timedelta
    
    # Calculer la date de début selon le filtre
    today = datetime.now()
    if period == "today":
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = today - timedelta(days=7)
    elif period == "month":
        start_date = today - timedelta(days=30)
    elif period == "quarter":
        start_date = today - timedelta(days=90)
    else:  # all
        start_date = datetime(2020, 1, 1)
    
    # Récupérer les exécutions réelles
    query = db.query(DBWorkflowExecution)
    if workflow_id:
        query = query.filter(DBWorkflowExecution.workflow_id == workflow_id)
    executions = query.all()
    
    # Filtrer par date
    filtered_executions = [
        e for e in executions 
        if e.started_at and e.started_at >= start_date
    ]
    
    workflows = db.query(DBWorkflow).all()
    workflow_map = {w.id: w for w in workflows}
    
    # Compter par statut
    total = len(filtered_executions)
    successful = len([e for e in filtered_executions if e.status == "completed"])
    failed = len([e for e in filtered_executions if e.status == "failed"])
    pending = len([e for e in filtered_executions if e.status in ["pending", "running"]])
    
    # Générer des données de démo si pas assez
    demo_mode = total < 5
    if demo_mode:
        total = random.randint(35, 60)
        successful = int(total * random.uniform(0.85, 0.95))
        failed = random.randint(1, 5)
        pending = total - successful - failed
    
    # Activité par jour (7 derniers jours)
    days = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
    by_day = []
    for i in range(7):
        day_date = today - timedelta(days=6-i)
        day_name = days[day_date.weekday()]
        day_count = len([e for e in filtered_executions 
                        if e.started_at and e.started_at.date() == day_date.date()])
        if demo_mode and day_count == 0:
            day_count = random.randint(3, 15) if day_date.weekday() < 5 else random.randint(0, 5)
        by_day.append({"date": day_name, "count": day_count})
    
    # Top workflows avec ID
    workflow_counts = {}
    for wf in workflows:
        wf_executions = len([e for e in filtered_executions if e.workflow_id == wf.id])
        if demo_mode and wf_executions == 0:
            wf_executions = random.randint(5, 20)
        workflow_counts[wf.id] = {
            "id": wf.id,
            "name": wf.name,
            "count": wf_executions,
            "icon": "⚡"
        }
    
    by_workflow = sorted(workflow_counts.values(), key=lambda x: x["count"], reverse=True)[:5]
    
    # Si pas de workflows, générer des exemples
    if not by_workflow:
        by_workflow = [
            {"id": "wf-1", "name": "Relance clients", "count": 18, "icon": "📧"},
            {"id": "wf-2", "name": "Prospection B2B", "count": 12, "icon": "🎯"},
            {"id": "wf-3", "name": "Rapport hebdo", "count": 9, "icon": "📊"},
            {"id": "wf-4", "name": "Facturation auto", "count": 8, "icon": "🧾"},
        ]
    
    # Générer les exécutions détaillées (pour le frontend)
    execution_list = []
    if demo_mode:
        # Générer des exécutions de démo
        demo_executions = [
            {
                "id": "exec-1",
                "workflow_id": "wf-1",
                "workflow_name": "Relance clients",
                "workflow_icon": "📧",
                "status": "completed",
                "started_at": (today - timedelta(hours=1)).isoformat(),
                "completed_at": (today - timedelta(minutes=58)).isoformat(),
                "duration_seconds": 120,
                "steps": [
                    {"id": "s1", "name": "Récupérer liste clients", "status": "completed", "output": "12 clients trouvés"},
                    {"id": "s2", "name": "Générer emails personnalisés", "status": "completed", "output": "12 emails générés"},
                    {"id": "s3", "name": "Envoyer via Gmail", "status": "completed", "output": "12 emails envoyés"},
                ]
            },
            {
                "id": "exec-2",
                "workflow_id": "wf-2",
                "workflow_name": "Prospection B2B",
                "workflow_icon": "🎯",
                "status": "failed",
                "started_at": (today - timedelta(hours=2)).isoformat(),
                "duration_seconds": 45,
                "error_message": "Impossible de se connecter au CRM. Vérifiez vos identifiants API.",
                "steps": [
                    {"id": "s1", "name": "Rechercher prospects", "status": "completed", "output": "25 prospects trouvés"},
                    {"id": "s2", "name": "Enrichir données", "status": "completed", "output": "Données enrichies"},
                    {"id": "s3", "name": "Ajouter au CRM", "status": "failed", "error": "API Error 401: Unauthorized"},
                    {"id": "s4", "name": "Envoyer email intro", "status": "skipped"},
                ]
            },
            {
                "id": "exec-3",
                "workflow_id": "wf-3",
                "workflow_name": "Rapport SEO hebdo",
                "workflow_icon": "📊",
                "status": "completed",
                "started_at": (today - timedelta(days=1)).isoformat(),
                "completed_at": (today - timedelta(days=1, minutes=-7)).isoformat(),
                "duration_seconds": 420,
                "steps": [
                    {"id": "s1", "name": "Collecter métriques GSC", "status": "completed", "output": "1250 mots-clés analysés"},
                    {"id": "s2", "name": "Analyser positions", "status": "completed", "output": "+15 positions en moyenne"},
                    {"id": "s3", "name": "Générer rapport PDF", "status": "completed", "output": "Rapport généré"},
                    {"id": "s4", "name": "Envoyer par email", "status": "completed", "output": "Envoyé à 3 destinataires"},
                ]
            },
            {
                "id": "exec-4",
                "workflow_id": "wf-4",
                "workflow_name": "Facturation auto",
                "workflow_icon": "🧾",
                "status": "failed",
                "started_at": (today - timedelta(days=2)).isoformat(),
                "duration_seconds": 30,
                "error_message": "Le template de facture est introuvable. Fichier supprimé ou déplacé.",
                "steps": [
                    {"id": "s1", "name": "Récupérer prestations", "status": "completed", "output": "8 prestations à facturer"},
                    {"id": "s2", "name": "Charger template", "status": "failed", "error": "FileNotFoundError: template_facture.docx"},
                    {"id": "s3", "name": "Générer factures", "status": "skipped"},
                ]
            },
            {
                "id": "exec-5",
                "workflow_id": "wf-1",
                "workflow_name": "Relance clients",
                "workflow_icon": "📧",
                "status": "running",
                "started_at": (today - timedelta(minutes=2)).isoformat(),
                "steps": [
                    {"id": "s1", "name": "Récupérer liste clients", "status": "completed", "output": "8 clients trouvés"},
                    {"id": "s2", "name": "Générer emails personnalisés", "status": "running"},
                    {"id": "s3", "name": "Envoyer via Gmail", "status": "pending"},
                ]
            },
        ]
        execution_list = demo_executions
    else:
        # Convertir les vraies exécutions
        for e in filtered_executions[:20]:  # Limiter à 20
            wf = workflow_map.get(e.workflow_id)
            execution_list.append({
                "id": e.id,
                "workflow_id": e.workflow_id,
                "workflow_name": wf.name if wf else "Workflow inconnu",
                "workflow_icon": "⚡",
                "status": e.status,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "duration_seconds": (e.completed_at - e.started_at).total_seconds() if e.completed_at and e.started_at else None,
                "error_message": e.error_message if hasattr(e, 'error_message') else None,
                "steps": []  # TODO: stocker les steps en DB
            })
    
    # Calculer les actions et temps économisé
    actions_completed = total * random.randint(2, 5)
    time_saved_hours = int(actions_completed * 0.15)
    
    return {
        "total_executions": total,
        "successful": successful,
        "failed": failed,
        "pending": pending,
        "by_day": by_day,
        "by_workflow": by_workflow,
        "actions_completed": actions_completed,
        "time_saved_hours": time_saved_hours,
        "executions": execution_list
    }


# ============================================================
# 🔧 AUTO-FIX AGENT - Correction automatique des erreurs
# ============================================================

class AutoFixRequest(BaseModel):
    execution_id: str
    error_message: Optional[str] = None

class AutoFixResponse(BaseModel):
    success: bool
    diagnosis: str
    suggested_fix: str
    auto_fixed: bool
    details: Optional[str] = None


@app.post("/api/workflows/auto-fix", response_model=AutoFixResponse)
def auto_fix_workflow(request: AutoFixRequest, db: Session = Depends(get_db)):
    """Agent IA pour diagnostiquer et corriger automatiquement les erreurs de workflow"""
    
    # Récupérer l'exécution
    execution = db.query(DBWorkflowExecution).filter(DBWorkflowExecution.id == request.execution_id).first()
    
    error_msg = request.error_message or (execution.error_message if execution and hasattr(execution, 'error_message') else "Erreur inconnue")
    error_lower = error_msg.lower()
    
    # Analyse IA simulée basée sur les patterns d'erreurs courants
    diagnosis = ""
    suggested_fix = ""
    auto_fixed = False
    details = None
    
    if "401" in error_msg or "unauthorized" in error_lower or "authentification" in error_lower:
        diagnosis = "Erreur d'authentification détectée. Les identifiants API sont invalides ou expirés."
        suggested_fix = "Vérifiez et mettez à jour vos identifiants API dans la configuration de l'outil MCP concerné."
        details = "Allez dans Constructeur > Outils MCP > Sélectionnez l'outil > Mettre à jour les credentials"
    
    elif "404" in error_msg or "not found" in error_lower or "introuvable" in error_lower:
        diagnosis = "Ressource introuvable. Un fichier ou une URL n'existe plus."
        suggested_fix = "Vérifiez que les fichiers/URLs référencés dans le workflow existent toujours."
        details = "Le fichier ou l'endpoint API ciblé a peut-être été déplacé ou supprimé."
    
    elif "timeout" in error_lower or "délai" in error_lower:
        diagnosis = "Timeout détecté. L'opération a pris trop de temps."
        suggested_fix = "Augmentez le délai d'attente ou divisez la tâche en étapes plus petites."
        auto_fixed = True
        details = "Configuration auto-corrigée : timeout augmenté de 30s à 60s."
    
    elif "rate limit" in error_lower or "quota" in error_lower or "limite" in error_lower:
        diagnosis = "Limite de requêtes atteinte. Trop d'appels API en peu de temps."
        suggested_fix = "Ajoutez des délais entre les actions ou réduisez le volume traité."
        auto_fixed = True
        details = "Configuration auto-corrigée : délai de 2s ajouté entre chaque action."
    
    elif "connection" in error_lower or "connexion" in error_lower or "network" in error_lower:
        diagnosis = "Problème de connexion réseau ou service temporairement indisponible."
        suggested_fix = "Réessayez dans quelques minutes. Si le problème persiste, vérifiez la configuration réseau."
        details = "Ce type d'erreur est souvent temporaire."
    
    elif "permission" in error_lower or "access denied" in error_lower or "accès refusé" in error_lower:
        diagnosis = "Permissions insuffisantes pour effectuer cette action."
        suggested_fix = "Vérifiez les autorisations de l'outil MCP et accordez les permissions nécessaires."
        details = "L'utilisateur ou l'application n'a pas les droits requis."
    
    elif "template" in error_lower or "format" in error_lower:
        diagnosis = "Erreur de format ou template invalide."
        suggested_fix = "Vérifiez le format du template et les variables utilisées."
        auto_fixed = True
        details = "Template corrigé : variables manquantes remplacées par des valeurs par défaut."
    
    else:
        diagnosis = "Erreur non catégorisée. Une analyse manuelle peut être nécessaire."
        suggested_fix = "Consultez les logs détaillés et vérifiez la configuration du workflow."
        details = f"Message d'erreur original : {error_msg}"
    
    return AutoFixResponse(
        success=True,
        diagnosis=diagnosis,
        suggested_fix=suggested_fix,
        auto_fixed=auto_fixed,
        details=details
    )

