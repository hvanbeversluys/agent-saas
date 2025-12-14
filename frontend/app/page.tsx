"use client";

import { useEffect, useState } from "react";
import Chat from "./components/Chat";
import EmployeeWizard from "./components/EmployeeWizard";
import WorkflowBuilder from "./components/WorkflowBuilder";
import UserDashboard from "./components/UserDashboard";

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  scope: "enterprise" | "business";
  system_prompt: string;
  mcp_tools: { id: string; name: string; icon: string }[];
  prompts: { id: string; name: string }[];
  is_active: boolean;
}

interface MCPTool {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  scope: "enterprise" | "business";
  status: string;
  config_required: string[];
}

interface Prompt {
  id: string;
  name: string;
  description: string;
  category: string;
  scope: "enterprise" | "business";
  template: string;
  variables: string[];
}

interface Workflow {
  id: string;
  name: string;
  description: string;
  agent_id: string;
  trigger_type: string;
  trigger_config: Record<string, unknown>;
  input_schema: { name: string; type: string; required: boolean }[];
  tasks: {
    id: string;
    name: string;
    task_type: string;
    order: string;
    config: Record<string, unknown>;
  }[];
  is_active: boolean;
  created_at: string;
}

interface WorkflowExecution {
  id: string;
  workflow_id: string;
  status: string;
  started_at: string;
  completed_at?: string;
}

type UserMode = "user" | "builder";
type BuilderTab = "employees" | "workflows";
type UserTab = "dashboard" | "chat" | "my-workflows";

export default function Home() {
  const [mode, setMode] = useState<UserMode>("user");
  const [builderTab, setBuilderTab] = useState<BuilderTab>("employees");
  const [userTab, setUserTab] = useState<UserTab>("dashboard");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [mcpTools, setMcpTools] = useState<MCPTool[]>([]);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showWizard, setShowWizard] = useState(false);
  const [showWorkflowBuilder, setShowWorkflowBuilder] = useState(false);
  const [editingWorkflow, setEditingWorkflow] = useState<Workflow | null>(null);


  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [agentsRes, toolsRes, promptsRes, workflowsRes] = await Promise.all([
          fetch(`${apiUrl}/api/agents`),
          fetch(`${apiUrl}/api/mcp-tools`),
          fetch(`${apiUrl}/api/prompts`),
          fetch(`${apiUrl}/api/workflows`),
        ]);

        if (!agentsRes.ok || !toolsRes.ok || !promptsRes.ok) {
          throw new Error("Erreur API");
        }

        const [agentsData, toolsData, promptsData] = await Promise.all([
          agentsRes.json(),
          toolsRes.json(),
          promptsRes.json(),
        ]);

        setAgents(agentsData);
        setMcpTools(toolsData);
        setPrompts(promptsData);

        if (workflowsRes.ok) {
          const workflowsData = await workflowsRes.json();
          setWorkflows(workflowsData);
        }
      } catch (err) {
        setError("Impossible de charger les données. Backend hors ligne ?");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [apiUrl]);

  const refreshData = async () => {
    try {
      const [agentsRes, toolsRes, promptsRes, workflowsRes] = await Promise.all([
        fetch(`${apiUrl}/api/agents`),
        fetch(`${apiUrl}/api/mcp-tools`),
        fetch(`${apiUrl}/api/prompts`),
        fetch(`${apiUrl}/api/workflows`),
      ]);
      const [agentsData, toolsData, promptsData, workflowsData] = await Promise.all([
        agentsRes.json(),
        toolsRes.json(),
        promptsRes.json(),
        workflowsRes.ok ? workflowsRes.json() : [],
      ]);
      setAgents(agentsData);
      setMcpTools(toolsData);
      setPrompts(promptsData);
      setWorkflows(workflowsData);
    } catch (err) {
      console.error("Refresh failed:", err);
    }
  };

  const executeWorkflow = async (workflowId: string) => {
    try {
      const response = await fetch(`${apiUrl}/api/workflows/${workflowId}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_data: {} }),
      });
      if (response.ok) {
        alert("✅ Workflow lancé !");
        refreshData();
      }
    } catch (err) {
      alert("❌ Erreur lors du lancement");
    }
  };

  const deleteWorkflow = async (workflowId: string) => {
    if (!confirm("Supprimer ce workflow ?")) return;
    try {
      await fetch(`${apiUrl}/api/workflows/${workflowId}`, { method: "DELETE" });
      refreshData();
    } catch (err) {
      alert("❌ Erreur lors de la suppression");
    }
  };

  const activeAgents = agents.filter((a) => a.is_active);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-slate-400">Chargement...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
        <div className="text-center bg-red-500/10 border border-red-500/50 rounded-2xl p-8 max-w-md">
          <span className="text-4xl mb-4 block">⚠️</span>
          <h2 className="text-xl font-bold text-red-400 mb-2">Erreur de connexion</h2>
          <p className="text-slate-400">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-900/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <span className="text-3xl">🏭</span>
              <div>
                <h1 className="text-xl font-bold text-white">Agent SaaS</h1>
                <p className="text-xs text-slate-400">Vos employés virtuels</p>
              </div>
            </div>

            {/* Mode Toggle */}
            <div className="flex items-center gap-2 bg-slate-800 rounded-full p-1">
              <button
                onClick={() => setMode("user")}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                  mode === "user"
                    ? "bg-blue-600 text-white shadow-lg"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                💬 Utilisateur
              </button>
              <button
                onClick={() => setMode("builder")}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                  mode === "builder"
                    ? "bg-purple-600 text-white shadow-lg"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                🏗️ Constructeur
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {mode === "user" ? (
          /* ========== MODE UTILISATEUR ========== */
          <div className="space-y-6">
            {/* User Tabs */}
            <div className="flex items-center gap-4 border-b border-slate-700 pb-4">
              <button
                onClick={() => setUserTab("dashboard")}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                  userTab === "dashboard"
                    ? "bg-blue-600 text-white"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`}
              >
                📊 Tableau de bord
              </button>
              <button
                onClick={() => setUserTab("chat")}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                  userTab === "chat"
                    ? "bg-blue-600 text-white"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`}
              >
                💬 Discuter
              </button>
              <button
                onClick={() => setUserTab("my-workflows")}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                  userTab === "my-workflows"
                    ? "bg-blue-600 text-white"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`}
              >
                ⚡ Mes Automatisations
                {workflows.filter(w => w.is_active).length > 0 && (
                  <span className="text-xs bg-emerald-500/30 text-emerald-300 px-2 py-0.5 rounded-full">
                    {workflows.filter(w => w.is_active).length}
                  </span>
                )}
              </button>
            </div>

            {userTab === "dashboard" ? (
              /* ========== TAB DASHBOARD ========== */
              <UserDashboard workflows={workflows} />
            ) : userTab === "chat" ? (
              /* ========== TAB CHAT ========== */
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Left: Team Overview */}
                <div className="lg:col-span-1 space-y-6">
                  <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-6">
                    <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                      👥 Votre équipe virtuelle
                    </h2>
                    <p className="text-sm text-slate-400 mb-4">
                      Posez votre question, l&apos;assistant vous redirigera vers le bon collègue.
                    </p>
                    <div className="space-y-3">
                      {activeAgents.map((agent) => (
                        <button
                          key={agent.id}
                          onClick={() => setSelectedAgent(agent)}
                          className={`w-full flex items-center gap-3 p-3 rounded-xl transition-all text-left ${
                            selectedAgent?.id === agent.id
                              ? "bg-blue-600/20 border border-blue-500"
                              : "bg-slate-700/30 border border-transparent hover:bg-slate-700/50"
                          }`}
                        >
                          <span className="text-2xl">{agent.icon}</span>
                          <div className="flex-1 min-w-0">
                            <h3 className="font-medium text-white truncate">{agent.name}</h3>
                            <p className="text-xs text-slate-400 truncate">{agent.description}</p>
                          </div>
                          {selectedAgent?.id === agent.id && (
                            <span className="text-green-400 text-xs">●</span>
                          )}
                        </button>
                      ))}
                    </div>
                    {activeAgents.length === 0 && (
                      <div className="text-center py-8 text-slate-500">
                        <span className="text-4xl block mb-2">🤷</span>
                        <p>Aucun employé disponible</p>
                        <button
                          onClick={() => setMode("builder")}
                          className="mt-4 text-sm text-purple-400 hover:text-purple-300"
                        >
                          Créer votre premier employé →
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Right: Chat */}
                <div className="lg:col-span-2">
                  <div className="bg-slate-800/50 border border-slate-700 rounded-2xl overflow-hidden h-[calc(100vh-280px)]">
                    <Chat
                      selectedAgent={selectedAgent}
                      onAgentHandoff={(agentId) => {
                        const agent = agents.find((a) => a.id === agentId);
                        if (agent) setSelectedAgent(agent);
                      }}
                    />
                  </div>
                </div>
              </div>
            ) : (
              /* ========== TAB MES WORKFLOWS ========== */
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-2xl font-bold text-white">⚡ Mes Automatisations</h2>
                    <p className="text-slate-400 mt-1">
                      Vos workflows actifs travaillent pour vous
                    </p>
                  </div>
                </div>

                {workflows.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {workflows.map((workflow) => {
                      const agent = agents.find((a) => a.id === workflow.agent_id);
                      return (
                        <div
                          key={workflow.id}
                          className={`bg-slate-800/50 border rounded-2xl p-6 transition-all ${
                            workflow.is_active
                              ? "border-emerald-500/50 hover:border-emerald-500"
                              : "border-slate-700 opacity-60"
                          }`}
                        >
                          {/* Header */}
                          <div className="flex items-start justify-between mb-4">
                            <div className="flex items-center gap-3">
                              <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-xl ${
                                workflow.is_active
                                  ? "bg-emerald-500/20"
                                  : "bg-slate-700"
                              }`}>
                                ⚡
                              </div>
                              <div>
                                <h3 className="font-semibold text-white">{workflow.name}</h3>
                                <p className="text-xs text-slate-400">
                                  {workflow.description || "Workflow automatisé"}
                                </p>
                              </div>
                            </div>
                            <span
                              className={`text-xs px-2 py-1 rounded-full ${
                                workflow.is_active
                                  ? "bg-emerald-500/20 text-emerald-400"
                                  : "bg-slate-600/50 text-slate-400"
                              }`}
                            >
                              {workflow.is_active ? "● Actif" : "○ Inactif"}
                            </span>
                          </div>

                          {/* Info */}
                          <div className="space-y-3 mb-4">
                            <div className="flex items-center gap-2 text-sm">
                              <span className="text-slate-500">Employé :</span>
                              <span className="text-white flex items-center gap-1">
                                {agent?.icon || "🤖"} {agent?.name || "Non assigné"}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                              <span className="text-slate-500">Déclencheur :</span>
                              <span className="text-white">
                                {workflow.trigger_type === "manual" && "🖱️ Manuel"}
                                {workflow.trigger_type === "cron" && "📅 Planifié"}
                                {workflow.trigger_type === "scheduled" && "📅 Planifié"}
                                {workflow.trigger_type === "event" && "⚡ Automatique"}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                              <span className="text-slate-500">Étapes :</span>
                              <span className="text-white">{workflow.tasks?.length || 0} tâches</span>
                            </div>
                          </div>

                          {/* Actions */}
                          <div className="flex gap-2">
                            <button
                              onClick={() => executeWorkflow(workflow.id)}
                              disabled={!workflow.is_active}
                              className="flex-1 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white rounded-xl text-sm font-medium transition-all flex items-center justify-center gap-2"
                            >
                              ▶️ Lancer
                            </button>
                            <button
                              onClick={() => {
                                setMode("builder");
                                setBuilderTab("workflows");
                              }}
                              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-xl text-sm transition-all"
                            >
                              ⚙️
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center py-16 bg-slate-800/30 border border-dashed border-slate-700 rounded-2xl">
                    <span className="text-6xl block mb-4">⚡</span>
                    <h3 className="text-xl font-semibold text-white mb-2">
                      Pas encore d&apos;automatisation
                    </h3>
                    <p className="text-slate-400 mb-6 max-w-md mx-auto">
                      Créez des workflows pour automatiser les tâches répétitives de vos employés virtuels
                    </p>
                    <button
                      onClick={() => {
                        setMode("builder");
                        setBuilderTab("workflows");
                      }}
                      className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl font-medium"
                    >
                      🏗️ Créer mon premier workflow →
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          /* ========== MODE CONSTRUCTEUR ========== */
          <div className="space-y-6">
            {/* Builder Tabs */}
            <div className="flex items-center gap-4 border-b border-slate-700 pb-4">
              <button
                onClick={() => setBuilderTab("employees")}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                  builderTab === "employees"
                    ? "bg-purple-600 text-white"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`}
              >
                👥 Employés
                <span className="text-xs bg-slate-700 px-2 py-0.5 rounded-full">
                  {agents.length}
                </span>
              </button>
              <button
                onClick={() => setBuilderTab("workflows")}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                  builderTab === "workflows"
                    ? "bg-purple-600 text-white"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`}
              >
                ⚡ Workflows
                <span className="text-xs bg-slate-700 px-2 py-0.5 rounded-full">
                  {workflows.length}
                </span>
              </button>
            </div>

            {builderTab === "employees" ? (
              /* ========== TAB EMPLOYEES ========== */
              <>
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-2xl font-bold text-white">👥 Vos Employés Virtuels</h2>
                    <p className="text-slate-400 mt-1">
                      Créez et configurez vos assistants IA personnalisés
                    </p>
                  </div>
                  <button
                    onClick={() => setShowWizard(true)}
                    className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white rounded-xl font-medium shadow-lg shadow-purple-500/25 transition-all"
                  >
                    <span className="text-xl">➕</span>
                    Nouvel Employé
                  </button>
                </div>

                {/* Employees Grid */}
                {agents.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {agents.map((agent) => (
                      <div
                        key={agent.id}
                        className="bg-slate-800/50 border border-slate-700 rounded-2xl p-6 hover:border-slate-600 transition-all group"
                      >
                        <div className="flex items-start justify-between mb-4">
                          <span className="text-4xl">{agent.icon}</span>
                          <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button className="p-2 bg-slate-700 hover:bg-blue-600 rounded-lg text-sm">
                              ✏️
                            </button>
                            <button className="p-2 bg-slate-700 hover:bg-red-600 rounded-lg text-sm">
                              🗑️
                            </button>
                          </div>
                        </div>
                        <h3 className="text-lg font-semibold text-white mb-2">{agent.name}</h3>
                        <p className="text-sm text-slate-400 mb-4 line-clamp-2">
                          {agent.description}
                        </p>

                        {/* Tools & Prompts */}
                        <div className="flex flex-wrap gap-2 mb-4">
                          {agent.mcp_tools.slice(0, 3).map((tool) => (
                            <span
                              key={tool.id}
                              className="text-xs bg-slate-700 text-slate-300 px-2 py-1 rounded-full"
                            >
                              {tool.icon} {tool.name}
                            </span>
                          ))}
                          {agent.mcp_tools.length > 3 && (
                            <span className="text-xs text-slate-500">
                              +{agent.mcp_tools.length - 3}
                            </span>
                          )}
                        </div>

                        {/* Status */}
                        <div className="flex items-center justify-between pt-4 border-t border-slate-700">
                          <span
                            className={`text-xs px-2 py-1 rounded-full ${
                              agent.is_active
                                ? "bg-green-500/20 text-green-400"
                                : "bg-slate-600/50 text-slate-400"
                            }`}
                          >
                            {agent.is_active ? "● Actif" : "○ Inactif"}
                          </span>
                          <span
                            className={`text-xs px-2 py-1 rounded-full ${
                              agent.scope === "enterprise"
                                ? "bg-purple-500/20 text-purple-300"
                                : "bg-amber-500/20 text-amber-300"
                            }`}
                          >
                            {agent.scope === "enterprise" ? "🏢 Entreprise" : "🎯 Métier"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-16 bg-slate-800/30 border border-dashed border-slate-700 rounded-2xl">
                    <span className="text-6xl block mb-4">🤖</span>
                    <h3 className="text-xl font-semibold text-white mb-2">
                      Créez votre premier employé virtuel
                    </h3>
                    <p className="text-slate-400 mb-6 max-w-md mx-auto">
                      En quelques étapes, configurez un assistant IA qui travaillera pour vous 24/7
                    </p>
                    <button
                      onClick={() => setShowWizard(true)}
                      className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl font-medium"
                    >
                      Commencer →
                    </button>
                  </div>
                )}
              </>
            ) : (
              /* ========== TAB WORKFLOWS ========== */
              <>
                {/* Header */}
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-2xl font-bold text-white">⚡ Workflows Automatisés</h2>
                    <p className="text-slate-400 mt-1">
                      Planifiez des actions automatiques pour vos employés
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setEditingWorkflow(null);
                      setShowWorkflowBuilder(true);
                    }}
                    className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white rounded-xl font-medium shadow-lg shadow-purple-500/25 transition-all"
                  >
                    <span className="text-xl">➕</span>
                    Nouveau Workflow
                  </button>
                </div>

                {/* Workflows Grid */}
                {workflows.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {workflows.map((workflow) => {
                      const agent = agents.find((a) => a.id === workflow.agent_id);
                      return (
                        <div
                          key={workflow.id}
                          className="bg-slate-800/50 border border-slate-700 rounded-2xl p-6 hover:border-slate-600 transition-all"
                        >
                          <div className="flex items-start justify-between mb-4">
                            <div className="flex items-center gap-3">
                              <span className="text-3xl">⚡</span>
                              <div>
                                <h3 className="text-lg font-semibold text-white">
                                  {workflow.name}
                                </h3>
                                <p className="text-sm text-slate-400">
                                  {workflow.description || "Pas de description"}
                                </p>
                              </div>
                            </div>
                            <span
                              className={`text-xs px-2 py-1 rounded-full ${
                                workflow.is_active
                                  ? "bg-green-500/20 text-green-400"
                                  : "bg-slate-600/50 text-slate-400"
                              }`}
                            >
                              {workflow.is_active ? "● Actif" : "○ Inactif"}
                            </span>
                          </div>

                          {/* Info */}
                          <div className="grid grid-cols-2 gap-4 mb-4">
                            <div className="bg-slate-700/30 rounded-xl p-3">
                              <p className="text-xs text-slate-400 mb-1">Employé</p>
                              <div className="flex items-center gap-2">
                                <span>{agent?.icon || "🤖"}</span>
                                <span className="text-sm text-white">
                                  {agent?.name || "Non assigné"}
                                </span>
                              </div>
                            </div>
                            <div className="bg-slate-700/30 rounded-xl p-3">
                              <p className="text-xs text-slate-400 mb-1">Déclencheur</p>
                              <span className="text-sm text-white">
                                {workflow.trigger_type === "manual" && "🖱️ Manuel"}
                                {workflow.trigger_type === "cron" && (
                                  <>
                                    ⏰{" "}
                                    {(workflow.trigger_config?.cron as string) || "Planifié"}
                                  </>
                                )}
                                {workflow.trigger_type === "event" && (
                                  <>⚡ {(workflow.trigger_config?.event as string) || "Event"}</>
                                )}
                              </span>
                            </div>
                          </div>

                          {/* Tasks preview */}
                          <div className="mb-4">
                            <p className="text-xs text-slate-400 mb-2">
                              📝 {workflow.tasks?.length || 0} tâches
                            </p>
                            <div className="flex flex-wrap gap-2">
                              {workflow.tasks?.slice(0, 4).map((task, idx) => (
                                <span
                                  key={task.id}
                                  className="text-xs bg-slate-700 text-slate-300 px-2 py-1 rounded-full"
                                >
                                  {idx + 1}. {task.name}
                                </span>
                              ))}
                              {(workflow.tasks?.length || 0) > 4 && (
                                <span className="text-xs text-slate-500">
                                  +{workflow.tasks.length - 4}
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Actions */}
                          <div className="flex items-center justify-between pt-4 border-t border-slate-700">
                            <div className="flex gap-2">
                              <button
                                onClick={() => executeWorkflow(workflow.id)}
                                className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium transition-all"
                              >
                                ▶️ Lancer
                              </button>
                              <button
                                onClick={() => {
                                  setEditingWorkflow(workflow);
                                  setShowWorkflowBuilder(true);
                                }}
                                className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-all"
                              >
                                ✏️ Modifier
                              </button>
                            </div>
                            <button
                              onClick={() => deleteWorkflow(workflow.id)}
                              className="p-2 text-slate-400 hover:text-red-400 transition-all"
                            >
                              🗑️
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center py-16 bg-slate-800/30 border border-dashed border-slate-700 rounded-2xl">
                    <span className="text-6xl block mb-4">⚡</span>
                    <h3 className="text-xl font-semibold text-white mb-2">
                      Créez votre premier workflow
                    </h3>
                    <p className="text-slate-400 mb-6 max-w-md mx-auto">
                      Automatisez les tâches de vos employés avec des workflows planifiés ou
                      déclenchés par événements
                    </p>
                    <button
                      onClick={() => {
                        setEditingWorkflow(null);
                        setShowWorkflowBuilder(true);
                      }}
                      className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl font-medium"
                    >
                      Créer un workflow →
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </main>

      {/* Employee Wizard Modal */}
      {showWizard && (
        <EmployeeWizard
          mcpTools={mcpTools}
          prompts={prompts}
          onClose={() => setShowWizard(false)}
          onSuccess={() => {
            setShowWizard(false);
            refreshData();
          }}
        />
      )}

      {/* Workflow Builder Modal */}
      {showWorkflowBuilder && (
        <WorkflowBuilder
          agents={agents}
          mcpTools={mcpTools}
          prompts={prompts}
          editingWorkflow={editingWorkflow}
          onClose={() => {
            setShowWorkflowBuilder(false);
            setEditingWorkflow(null);
          }}
          onSuccess={() => {
            setShowWorkflowBuilder(false);
            setEditingWorkflow(null);
            refreshData();
          }}
        />
      )}
    </div>
  );
}
