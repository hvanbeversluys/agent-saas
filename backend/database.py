"""
Database configuration avec SQLite pour le MVP.
Facilement migrable vers PostgreSQL plus tard.
"""
from sqlalchemy import create_engine, Column, String, Text, Boolean, DateTime, JSON, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid

# SQLite database (fichier local)
DATABASE_URL = "sqlite:///./agent_saas.db"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Nécessaire pour SQLite avec FastAPI
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Helper pour générer des UUIDs ---
def generate_uuid():
    return str(uuid.uuid4())

# --- Table de liaison Agent <-> MCP Tools (Many-to-Many) ---
agent_mcp_tools = Table(
    'agent_mcp_tools',
    Base.metadata,
    Column('agent_id', String, ForeignKey('agents.id'), primary_key=True),
    Column('mcp_tool_id', String, ForeignKey('mcp_tools.id'), primary_key=True)
)

# --- Table de liaison Agent <-> Prompts (Many-to-Many) ---
agent_prompts = Table(
    'agent_prompts',
    Base.metadata,
    Column('agent_id', String, ForeignKey('agents.id'), primary_key=True),
    Column('prompt_id', String, ForeignKey('prompts.id'), primary_key=True)
)

# --- Models ---

class DBAgent(Base):
    """Modèle Agent en base de données"""
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    icon = Column(String(10), default="🤖")
    category = Column(String(50), default="general")
    scope = Column(String(20), default="business")  # enterprise = global, business = métier
    system_prompt = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    mcp_tools = relationship("DBMCPTool", secondary=agent_mcp_tools, back_populates="agents")
    prompts = relationship("DBPrompt", secondary=agent_prompts, back_populates="agents")


class DBPrompt(Base):
    """Modèle Prompt en base de données"""
    __tablename__ = "prompts"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    category = Column(String(50), default="general")
    scope = Column(String(20), default="business")  # enterprise = global, business = métier
    template = Column(Text, nullable=False)
    variables = Column(JSON, default=list)  # Liste des variables: ["nom", "email", ...]
    
    # Liaison avec un outil MCP (optionnel) - Crée un "Bloc Action Métier"
    mcp_tool_id = Column(String, ForeignKey('mcp_tools.id'), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    agents = relationship("DBAgent", secondary=agent_prompts, back_populates="prompts")
    mcp_tool = relationship("DBMCPTool", backref="prompts")


class DBMCPTool(Base):
    """Modèle MCP Tool en base de données"""
    __tablename__ = "mcp_tools"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    icon = Column(String(10), default="🔌")
    category = Column(String(50), default="general")
    scope = Column(String(20), default="business")  # enterprise = global, business = métier
    status = Column(String(20), default="active")  # active, beta, coming_soon, disabled
    config_required = Column(JSON, default=list)  # Clés de config nécessaires
    config_values = Column(JSON, default=dict)  # Valeurs de config (cryptées en prod)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    agents = relationship("DBAgent", secondary=agent_mcp_tools, back_populates="mcp_tools")


class DBConversation(Base):
    """Historique des conversations"""
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    agent_id = Column(String, ForeignKey('agents.id'), nullable=True)
    messages = Column(JSON, default=list)  # [{role: "user", content: "..."}, ...]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# --- Scheduler Models ---

class DBWorkflow(Base):
    """Un workflow est une séquence d'actions automatisées pour un agent"""
    __tablename__ = "workflows"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    agent_id = Column(String, ForeignKey('agents.id'), nullable=False)
    
    # Type de déclenchement
    trigger_type = Column(String(20), default="manual")  # manual, cron, event
    trigger_config = Column(JSON, default=dict)  # {"cron": "0 9 * * 1-5"} ou {"event": "new_lead", "source": "crm"}
    
    # Paramètres d'entrée du workflow
    input_schema = Column(JSON, default=list)  # [{"name": "client_name", "type": "string", "required": true}]
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    agent = relationship("DBAgent", backref="workflows")
    tasks = relationship("DBWorkflowTask", back_populates="workflow", order_by="DBWorkflowTask.order")
    executions = relationship("DBWorkflowExecution", back_populates="workflow")


class DBWorkflowTask(Base):
    """Une tâche dans un workflow - peut être une action, une condition, une boucle, etc."""
    __tablename__ = "workflow_tasks"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    workflow_id = Column(String, ForeignKey('workflows.id'), nullable=False)
    
    name = Column(String(100), nullable=False)
    description = Column(Text)
    order = Column(String(10), default="1")  # "1", "2", "2.1" pour les sous-tâches
    
    # Type de tâche
    task_type = Column(String(30), nullable=False)
    # Types disponibles:
    # - "prompt": Exécute un prompt avec l'agent
    # - "mcp_action": Appelle un outil MCP
    # - "condition": Branche conditionnelle (if/else)
    # - "loop": Boucle sur une liste
    # - "wait": Attente (délai ou événement)
    # - "parallel": Exécution parallèle de sous-tâches
    # - "human_approval": Attend validation humaine
    # - "set_variable": Définit une variable
    # - "http_request": Appel HTTP externe
    
    # Configuration de la tâche (dépend du type)
    config = Column(JSON, default=dict)
    # Exemples:
    # prompt: {"prompt_id": "...", "prompt_template": "...", "variables_mapping": {"client": "{{input.client_name}}"}}
    # mcp_action: {"tool_id": "mcp-email", "action": "send", "params": {"to": "{{input.email}}"}}
    # condition: {"expression": "{{prev.sentiment}} == 'positive'", "true_branch": "3", "false_branch": "4"}
    # loop: {"iterate_over": "{{input.clients}}", "item_var": "client", "tasks": [...]}
    # wait: {"type": "delay", "duration": 3600} ou {"type": "event", "event": "response_received"}
    # parallel: {"tasks": ["2.1", "2.2", "2.3"]}
    # human_approval: {"message": "Valider l'envoi ?", "timeout": 86400}
    # set_variable: {"name": "total", "value": "{{prev.count}} + 1"}
    
    # Gestion des erreurs
    on_error = Column(String(20), default="stop")  # stop, continue, retry, goto
    retry_count = Column(String(5), default="0")
    error_goto = Column(String(10), nullable=True)  # Task order to jump to on error
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relations
    workflow = relationship("DBWorkflow", back_populates="tasks")


class DBWorkflowExecution(Base):
    """Historique d'exécution d'un workflow"""
    __tablename__ = "workflow_executions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    workflow_id = Column(String, ForeignKey('workflows.id'), nullable=False)
    
    status = Column(String(20), default="pending")  # pending, running, completed, failed, cancelled, waiting_approval
    
    # Données d'exécution
    input_data = Column(JSON, default=dict)  # Paramètres d'entrée
    output_data = Column(JSON, default=dict)  # Résultat final
    variables = Column(JSON, default=dict)  # Variables pendant l'exécution
    
    # Progression
    current_task_order = Column(String(10), nullable=True)
    tasks_completed = Column(JSON, default=list)  # Liste des task_id complétés
    task_results = Column(JSON, default=dict)  # {task_id: {output: ..., status: ...}}
    
    # Erreurs
    error_message = Column(Text, nullable=True)
    error_task_id = Column(String, nullable=True)
    
    # Timing
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relations
    workflow = relationship("DBWorkflow", back_populates="executions")


class DBScheduledJob(Base):
    """Jobs planifiés (pour les workflows avec trigger cron)"""
    __tablename__ = "scheduled_jobs"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    workflow_id = Column(String, ForeignKey('workflows.id'), nullable=False)
    
    cron_expression = Column(String(100), nullable=False)  # "0 9 * * 1-5" = 9h du lun au ven
    timezone = Column(String(50), default="Europe/Paris")
    
    next_run = Column(DateTime, nullable=True)
    last_run = Column(DateTime, nullable=True)
    last_execution_id = Column(String, nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relations
    workflow = relationship("DBWorkflow", backref="scheduled_job", uselist=False)


# --- Database initialization ---

def init_db():
    """Crée toutes les tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency pour FastAPI - fournit une session DB"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Seed data (données initiales) ---

def seed_demo_data(db):
    """Insère les données de démo si la DB est vide"""
    
    # Vérifier si des agents existent déjà
    if db.query(DBAgent).count() > 0:
        return
    
    print("🌱 Seeding demo data...")
    
    # --- MCP Tools ---
    # scope: "enterprise" = outils globaux de l'entreprise, "business" = outils métier spécifiques
    mcp_tools_data = [
        # 🏢 ENTERPRISE - Outils globaux
        {"id": "mcp-email", "name": "Email Sender", "description": "Envoie des emails via Gmail, Outlook ou SMTP.", "icon": "📧", "category": "email", "scope": "enterprise", "status": "active", "config_required": ["email_provider", "api_key"]},
        {"id": "mcp-crm", "name": "CRM Connector", "description": "Connecte votre CRM (HubSpot, Pipedrive, Notion).", "icon": "👥", "category": "crm", "scope": "enterprise", "status": "active", "config_required": ["crm_type", "api_key"]},
        {"id": "mcp-docs", "name": "Google Docs", "description": "Crée et édite des documents Google Docs.", "icon": "📄", "category": "productivity", "scope": "enterprise", "status": "active", "config_required": ["google_oauth"]},
        {"id": "mcp-calendar", "name": "Calendar Sync", "description": "Synchronise avec Google Calendar ou Outlook.", "icon": "📅", "category": "productivity", "scope": "enterprise", "status": "active", "config_required": ["calendar_provider", "oauth_token"]},
        {"id": "mcp-tasks", "name": "Task Manager", "description": "Connecte Notion, Trello ou Asana.", "icon": "✅", "category": "productivity", "scope": "enterprise", "status": "active", "config_required": ["task_provider", "api_key"]},
        {"id": "mcp-phone", "name": "VoIP Caller", "description": "Passe des appels et envoie des SMS.", "icon": "📞", "category": "communication", "scope": "enterprise", "status": "coming_soon", "config_required": ["voip_provider", "api_key"]},
        
        # 🎯 BUSINESS - Outils métier
        {"id": "mcp-seo-tools", "name": "SEO Analyzer", "description": "Analyse SEO de sites web (Semrush, Ahrefs).", "icon": "🔍", "category": "seo", "scope": "business", "status": "beta", "config_required": ["semrush_key"]},
        {"id": "mcp-analytics", "name": "Analytics Dashboard", "description": "Connecte Google Analytics et Search Console.", "icon": "📊", "category": "seo", "scope": "business", "status": "active", "config_required": ["google_oauth", "property_id"]},
        {"id": "mcp-facturation", "name": "Facturation", "description": "Génère factures et devis (Stripe, Pennylane).", "icon": "🧾", "category": "facturation", "scope": "business", "status": "beta", "config_required": ["billing_provider", "api_key"]},
        {"id": "mcp-linkedin", "name": "LinkedIn Automation", "description": "Automatise la prospection LinkedIn.", "icon": "💼", "category": "crm", "scope": "business", "status": "coming_soon", "config_required": ["linkedin_cookie"]},
    ]
    
    mcp_objects = {}
    for tool_data in mcp_tools_data:
        tool = DBMCPTool(**tool_data)
        db.add(tool)
        mcp_objects[tool_data["id"]] = tool
    
    # --- Prompts liés aux MCP Tools (Actions Métier) ---
    # Chaque prompt peut être lié à un MCP tool pour créer un "Bloc Action Métier"
    prompts_data = [
        # 🏢 ENTERPRISE - Actions globales
        {"id": "prompt-cr-reunion", "name": "Compte-rendu de réunion", "description": "Structure un compte-rendu de réunion et l'enregistre dans Google Docs", "category": "admin", "scope": "enterprise", "mcp_tool_id": "mcp-docs", "template": "Génère un compte-rendu de réunion:\n\nNotes: {notes_brutes}\nParticipants: {participants}\nDate: {date}\nObjet: {objet}", "variables": ["notes_brutes", "participants", "date", "objet"]},
        {"id": "prompt-email-pro", "name": "Envoyer email professionnel", "description": "Rédige et envoie un email professionnel", "category": "admin", "scope": "enterprise", "mcp_tool_id": "mcp-email", "template": "Rédige un email professionnel:\n\nDestinataire: {destinataire}\nObjet: {objet}\nMessage clé: {message}\nTon: {ton}", "variables": ["destinataire", "objet", "message", "ton"]},
        {"id": "prompt-todo-semaine", "name": "Créer planning hebdo", "description": "Organise les tâches de la semaine dans le gestionnaire de tâches", "category": "admin", "scope": "enterprise", "mcp_tool_id": "mcp-tasks", "template": "Organise ma semaine:\n\nTâches en cours: {taches}\nPriorités: {priorites}\nContraintes: {contraintes}", "variables": ["taches", "priorites", "contraintes"]},
        {"id": "prompt-rdv-calendar", "name": "Créer rendez-vous", "description": "Planifie un rendez-vous dans le calendrier", "category": "admin", "scope": "enterprise", "mcp_tool_id": "mcp-calendar", "template": "Crée un rendez-vous:\n\nTitre: {titre}\nDate: {date}\nHeure: {heure}\nParticipants: {participants}\nDescription: {description}", "variables": ["titre", "date", "heure", "participants", "description"]},
        
        # 🎯 BUSINESS - Actions Commercial
        {"id": "prompt-email-prospection", "name": "Envoyer email prospection", "description": "Génère et envoie un email de prospection personnalisé", "category": "commercial", "scope": "business", "mcp_tool_id": "mcp-email", "template": "Rédige un email de prospection pour contacter {nom_entreprise}, une entreprise de {secteur_activite} basée à {ville}.\n\nContexte: {contexte_specifique}\n\nL'email doit avoir un objet accrocheur et proposer un call-to-action clair.", "variables": ["nom_entreprise", "secteur_activite", "ville", "contexte_specifique"]},
        {"id": "prompt-relance-devis", "name": "Relancer devis", "description": "Génère et envoie un email de relance pour un devis non signé", "category": "commercial", "scope": "business", "mcp_tool_id": "mcp-email", "template": "Rédige un email de relance pour {nom_contact} de {nom_entreprise}.\n\nDevis envoyé le: {date_devis}\nMontant: {montant}€\nObjet: {objet_devis}", "variables": ["nom_contact", "nom_entreprise", "date_devis", "montant", "objet_devis"]},
        {"id": "prompt-maj-crm", "name": "Mettre à jour CRM", "description": "Met à jour la fiche client dans le CRM", "category": "commercial", "scope": "business", "mcp_tool_id": "mcp-crm", "template": "Met à jour le contact:\n\nNom: {nom_contact}\nEntreprise: {entreprise}\nStatut: {statut}\nNotes: {notes}", "variables": ["nom_contact", "entreprise", "statut", "notes"]},
        
        # 🎯 BUSINESS - Actions SEO
        {"id": "prompt-article-blog", "name": "Publier article SEO", "description": "Génère un article optimisé SEO et le publie", "category": "seo", "scope": "business", "mcp_tool_id": "mcp-docs", "template": "Rédige un article de blog SEO sur: \"{sujet}\"\n\nMot-clé principal: {mot_cle_principal}\nMots-clés secondaires: {mots_cles_secondaires}\nLocalisation: {ville_region}", "variables": ["sujet", "mot_cle_principal", "mots_cles_secondaires", "ville_region"]},
        {"id": "prompt-audit-rapide", "name": "Lancer audit SEO", "description": "Lance un audit SEO rapide avec les outils SEO", "category": "seo", "scope": "business", "mcp_tool_id": "mcp-seo-tools", "template": "Analyse le site {url} et génère un mini-audit SEO.\n\nSecteur: {secteur}\nObjectif: {objectif}", "variables": ["url", "secteur", "objectif"]},
        {"id": "prompt-rapport-analytics", "name": "Générer rapport Analytics", "description": "Génère un rapport de performance depuis Analytics", "category": "seo", "scope": "business", "mcp_tool_id": "mcp-analytics", "template": "Génère un rapport Analytics:\n\nPériode: {periode}\nMétriques: {metriques}\nObjectifs: {objectifs}", "variables": ["periode", "metriques", "objectifs"]},
        
        # 🎯 BUSINESS - Actions Admin/Facturation
        {"id": "prompt-relance-facture", "name": "Relancer facture impayée", "description": "Génère et envoie un email de relance pour facture", "category": "admin", "scope": "business", "mcp_tool_id": "mcp-email", "template": "Rédige un email de relance niveau {niveau_relance} pour la facture impayée.\n\nClient: {nom_client}\nN° Facture: {numero_facture}\nMontant: {montant}€\nJours de retard: {jours_retard}", "variables": ["niveau_relance", "nom_client", "numero_facture", "montant", "jours_retard"]},
        {"id": "prompt-creer-facture", "name": "Créer facture", "description": "Génère une facture dans le système de facturation", "category": "admin", "scope": "business", "mcp_tool_id": "mcp-facturation", "template": "Crée une facture:\n\nClient: {client}\nPrestations: {prestations}\nMontant HT: {montant_ht}€\nÉchéance: {echeance}", "variables": ["client", "prestations", "montant_ht", "echeance"]},
        
        # 🎯 BUSINESS - Actions Direction
        {"id": "prompt-analyse-concurrent", "name": "Analyser concurrent", "description": "Analyse un concurrent avec les outils SEO et Analytics", "category": "direction", "scope": "business", "mcp_tool_id": "mcp-analytics", "template": "Analyse le concurrent {nom_concurrent} ({url_concurrent}).\n\nMon positionnement: {mon_positionnement}\nMes services: {mes_services}\nZone: {zone_geo}", "variables": ["nom_concurrent", "url_concurrent", "mon_positionnement", "mes_services", "zone_geo"]},
    ]
    
    prompt_objects = {}
    for prompt_data in prompts_data:
        prompt = DBPrompt(**prompt_data)
        db.add(prompt)
        prompt_objects[prompt_data["id"]] = prompt
    
    # --- Agents avec liaisons ---
    # scope: "enterprise" = agents globaux, "business" = agents métier spécialisés
    agents_data = [
        # 🏢 ENTERPRISE - Agents globaux
        {
            "id": "agent-orchestrator",
            "name": "Assistant Entreprise",
            "description": "Agent principal qui analyse votre demande et vous oriente vers le bon expert.",
            "icon": "🎯",
            "category": "general",
            "scope": "enterprise",
            "system_prompt": "Tu es l'assistant principal de l'entreprise. Tu analyses les demandes des utilisateurs et tu les orientes vers l'agent spécialisé le plus adapté.",
            "mcp_tool_ids": [],
            "prompt_ids": []
        },
        {
            "id": "agent-planning",
            "name": "Assistant Planning & Projets",
            "description": "Aide à organiser les projets, planifier les tâches et suivre les deadlines.",
            "icon": "📅",
            "category": "admin",
            "scope": "enterprise",
            "system_prompt": "Tu es un assistant de gestion de projet. Tu crées des plannings réalistes et suis l'avancement des tâches.",
            "mcp_tool_ids": ["mcp-calendar", "mcp-tasks"],
            "prompt_ids": ["prompt-cr-reunion", "prompt-todo-semaine"]
        },
        {
            "id": "agent-communication",
            "name": "Assistant Communication",
            "description": "Rédige des emails professionnels, comptes-rendus et communications internes.",
            "icon": "✉️",
            "category": "admin",
            "scope": "enterprise",
            "system_prompt": "Tu es un expert en communication professionnelle. Tu rédiges des messages clairs, concis et adaptés au contexte.",
            "mcp_tool_ids": ["mcp-email", "mcp-docs"],
            "prompt_ids": ["prompt-email-pro", "prompt-cr-reunion"]
        },
        
        # 🎯 BUSINESS - Agents métier Commercial
        {
            "id": "agent-prospection",
            "name": "Assistant Prospection",
            "description": "Génère des emails de prospection personnalisés et des scripts d'appel.",
            "icon": "📞",
            "category": "commercial",
            "scope": "business",
            "system_prompt": "Tu es un expert en prospection commerciale pour une agence web. Tu rédiges des emails percutants et des scripts d'appel efficaces.",
            "mcp_tool_ids": ["mcp-email", "mcp-crm", "mcp-linkedin"],
            "prompt_ids": ["prompt-email-prospection"]
        },
        {
            "id": "agent-devis",
            "name": "Assistant Devis & Propositions",
            "description": "Aide à rédiger des devis professionnels et propositions commerciales.",
            "icon": "💼",
            "category": "commercial",
            "scope": "business",
            "system_prompt": "Tu es un expert en rédaction de propositions commerciales pour une agence web. Tu structures des devis clairs et convaincants.",
            "mcp_tool_ids": ["mcp-docs", "mcp-crm"],
            "prompt_ids": ["prompt-relance-devis"]
        },
        
        # 🎯 BUSINESS - Agents métier SEO
        {
            "id": "agent-seo-audit",
            "name": "Expert Audit SEO",
            "description": "Analyse les sites web et génère des rapports d'audit SEO détaillés.",
            "icon": "🔍",
            "category": "seo",
            "scope": "business",
            "system_prompt": "Tu es un expert SEO spécialisé dans l'audit de sites web pour les PME. Tu analyses et donnes des recommandations actionnables.",
            "mcp_tool_ids": ["mcp-seo-tools", "mcp-analytics"],
            "prompt_ids": ["prompt-audit-rapide"]
        },
        {
            "id": "agent-seo-content",
            "name": "Rédacteur SEO",
            "description": "Crée du contenu optimisé SEO: articles, fiches produits, pages.",
            "icon": "✍️",
            "category": "seo",
            "scope": "business",
            "system_prompt": "Tu es un rédacteur web expert en SEO. Tu écris du contenu engageant et optimisé pour les moteurs de recherche.",
            "mcp_tool_ids": ["mcp-seo-tools", "mcp-docs"],
            "prompt_ids": ["prompt-article-blog"]
        },
        
        # 🎯 BUSINESS - Agents métier Admin/Finance
        {
            "id": "agent-facturation",
            "name": "Assistant Facturation",
            "description": "Gère la création de factures, le suivi des paiements et les relances.",
            "icon": "🧾",
            "category": "admin",
            "scope": "business",
            "system_prompt": "Tu es un assistant administratif spécialisé dans la facturation. Tu gères factures, relances et suivi des paiements.",
            "mcp_tool_ids": ["mcp-facturation", "mcp-email"],
            "prompt_ids": ["prompt-relance-facture"]
        },
        
        # 🎯 BUSINESS - Agents métier Direction
        {
            "id": "agent-strategie",
            "name": "Conseiller Stratégique",
            "description": "Aide à la prise de décision stratégique: pricing, positionnement, développement.",
            "icon": "🧭",
            "category": "direction",
            "scope": "business",
            "system_prompt": "Tu es un conseiller stratégique pour dirigeants de PME. Tu donnes des conseils pragmatiques et actionnables.",
            "mcp_tool_ids": ["mcp-analytics", "mcp-docs"],
            "prompt_ids": ["prompt-analyse-concurrent"]
        },
        {
            "id": "agent-reporting",
            "name": "Assistant Reporting",
            "description": "Génère des tableaux de bord et rapports d'activité.",
            "icon": "📊",
            "category": "direction",
            "scope": "business",
            "system_prompt": "Tu es un expert en reporting et analyse business. Tu présentes les données de manière visuelle et actionnable.",
            "mcp_tool_ids": ["mcp-analytics", "mcp-crm", "mcp-facturation"],
            "prompt_ids": []
        },
    ]
    
    for agent_data in agents_data:
        mcp_tool_ids = agent_data.pop("mcp_tool_ids", [])
        prompt_ids = agent_data.pop("prompt_ids", [])
        
        agent = DBAgent(**agent_data)
        
        # Lier les MCP tools
        for tool_id in mcp_tool_ids:
            if tool_id in mcp_objects:
                agent.mcp_tools.append(mcp_objects[tool_id])
        
        # Lier les prompts
        for prompt_id in prompt_ids:
            if prompt_id in prompt_objects:
                agent.prompts.append(prompt_objects[prompt_id])
        
        db.add(agent)
    
    db.commit()
    print("✅ Demo data seeded successfully!")
