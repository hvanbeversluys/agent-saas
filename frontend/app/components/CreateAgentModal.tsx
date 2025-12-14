"use client";

import { useState, useEffect } from "react";

interface Prompt {
  id: string;
  name: string;
  category: string;
}

interface MCPTool {
  id: string;
  name: string;
  icon: string;
  status: string;
}

interface AgentFormData {
  name: string;
  description: string;
  icon: string;
  category: string;
  scope: "enterprise" | "business";
  system_prompt: string;
  mcp_tool_ids: string[];
  prompt_ids: string[];
}

interface CreateAgentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  prompts: Prompt[];
  mcpTools: MCPTool[];
  editingAgent?: {
    id: string;
    name: string;
    description: string;
    icon: string;
    category: string;
    scope: "enterprise" | "business";
    system_prompt: string;
    mcp_tools: { id: string }[];
    prompts: { id: string }[];
  } | null;
}

const ICONS = ["🤖", "📞", "💼", "🔍", "✍️", "🧾", "📅", "🎯", "📊", "📧", "👥", "⚡", "🚀", "💡", "🛠️"];
const CATEGORIES = [
  { id: "general", label: "Général" },
  { id: "commercial", label: "Commercial & Ventes" },
  { id: "seo", label: "SEO & Contenu" },
  { id: "admin", label: "Administratif" },
  { id: "direction", label: "Direction & Stratégie" },
];
const SCOPES = [
  { id: "enterprise", label: "🏢 Entreprise", desc: "Outils globaux (CRM, Email, Calendar...)" },
  { id: "business", label: "🎯 Métier", desc: "Automatisations spécifiques (SEO, Facturation...)" },
];

export default function CreateAgentModal({
  isOpen,
  onClose,
  onSuccess,
  prompts,
  mcpTools,
  editingAgent,
}: CreateAgentModalProps) {
  const [formData, setFormData] = useState<AgentFormData>({
    name: "",
    description: "",
    icon: "🤖",
    category: "general",
    scope: "business",
    system_prompt: "",
    mcp_tool_ids: [],
    prompt_ids: [],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (editingAgent) {
      setFormData({
        name: editingAgent.name,
        description: editingAgent.description,
        icon: editingAgent.icon,
        category: editingAgent.category,
        scope: editingAgent.scope || "business",
        system_prompt: editingAgent.system_prompt,
        mcp_tool_ids: editingAgent.mcp_tools?.map((t) => t.id) || [],
        prompt_ids: editingAgent.prompts?.map((p) => p.id) || [],
      });
    } else {
      setFormData({
        name: "",
        description: "",
        icon: "🤖",
        category: "general",
        scope: "business",
        system_prompt: "",
        mcp_tool_ids: [],
        prompt_ids: [],
      });
    }
  }, [editingAgent, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const url = editingAgent
        ? `${apiUrl}/api/agents/${editingAgent.id}`
        : `${apiUrl}/api/agents`;

      const res = await fetch(url, {
        method: editingAgent ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      if (!res.ok) {
        throw new Error("Erreur lors de la sauvegarde");
      }

      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  };

  const toggleTool = (toolId: string) => {
    setFormData((prev) => ({
      ...prev,
      mcp_tool_ids: prev.mcp_tool_ids.includes(toolId)
        ? prev.mcp_tool_ids.filter((id) => id !== toolId)
        : [...prev.mcp_tool_ids, toolId],
    }));
  };

  const togglePrompt = (promptId: string) => {
    setFormData((prev) => ({
      ...prev,
      prompt_ids: prev.prompt_ids.includes(promptId)
        ? prev.prompt_ids.filter((id) => id !== promptId)
        : [...prev.prompt_ids, promptId],
    }));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-700">
          <h2 className="text-xl font-bold text-white">
            {editingAgent ? "✏️ Modifier l'agent" : "➕ Nouvel Agent"}
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white text-2xl"
          >
            ×
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {error && (
            <div className="bg-red-500/20 border border-red-500/50 text-red-400 p-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          {/* Icon & Name */}
          <div className="flex gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">
                Icône
              </label>
              <div className="flex flex-wrap gap-2 p-3 bg-slate-900/50 rounded-lg max-w-[200px]">
                {ICONS.map((icon) => (
                  <button
                    key={icon}
                    type="button"
                    onClick={() => setFormData({ ...formData, icon })}
                    className={`text-2xl p-1 rounded transition-colors ${
                      formData.icon === icon
                        ? "bg-blue-600"
                        : "hover:bg-slate-700"
                    }`}
                  >
                    {icon}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-400 mb-2">
                Nom de l&apos;agent *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                placeholder="Ex: Assistant Commercial"
                required
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Description
            </label>
            <input
              type="text"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
              placeholder="Que fait cet agent ?"
            />
          </div>

          {/* Scope */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Scope
            </label>
            <div className="grid grid-cols-2 gap-3">
              {SCOPES.map((scope) => (
                <button
                  key={scope.id}
                  type="button"
                  onClick={() => setFormData({ ...formData, scope: scope.id as "enterprise" | "business" })}
                  className={`p-3 rounded-lg border text-left transition-all ${
                    formData.scope === scope.id
                      ? scope.id === "enterprise"
                        ? "border-purple-500 bg-purple-500/20"
                        : "border-amber-500 bg-amber-500/20"
                      : "border-slate-700 bg-slate-900/50 hover:border-slate-600"
                  }`}
                >
                  <span className="font-medium text-white">{scope.label}</span>
                  <p className="text-xs text-slate-400 mt-1">{scope.desc}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Category */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Catégorie
            </label>
            <select
              value={formData.category}
              onChange={(e) => setFormData({ ...formData, category: e.target.value })}
              className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
            >
              {CATEGORIES.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.label}
                </option>
              ))}
            </select>
          </div>

          {/* System Prompt */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Prompt système *
            </label>
            <textarea
              value={formData.system_prompt}
              onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
              className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500 min-h-[120px]"
              placeholder="Tu es un expert en... Tu dois..."
              required
            />
            <p className="text-xs text-slate-500 mt-1">
              Décris le rôle, le ton et les compétences de l&apos;agent.
            </p>
          </div>

          {/* MCP Tools */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              🔌 Outils MCP connectés
            </label>
            <div className="flex flex-wrap gap-2 p-3 bg-slate-900/50 rounded-lg">
              {mcpTools
                .filter((t) => t.status === "active" || t.status === "beta")
                .map((tool) => (
                  <button
                    key={tool.id}
                    type="button"
                    onClick={() => toggleTool(tool.id)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                      formData.mcp_tool_ids.includes(tool.id)
                        ? "bg-blue-600 text-white"
                        : "bg-slate-700/50 text-slate-300 hover:bg-slate-700"
                    }`}
                  >
                    <span>{tool.icon}</span>
                    {tool.name}
                  </button>
                ))}
            </div>
          </div>

          {/* Prompts */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              📝 Prompts associés
            </label>
            <div className="flex flex-wrap gap-2 p-3 bg-slate-900/50 rounded-lg max-h-[150px] overflow-y-auto">
              {prompts.map((prompt) => (
                <button
                  key={prompt.id}
                  type="button"
                  onClick={() => togglePrompt(prompt.id)}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                    formData.prompt_ids.includes(prompt.id)
                      ? "bg-green-600 text-white"
                      : "bg-slate-700/50 text-slate-300 hover:bg-slate-700"
                  }`}
                >
                  {prompt.name}
                </button>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-slate-700">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50"
            >
              {loading ? "Enregistrement..." : editingAgent ? "Mettre à jour" : "Créer l'agent"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
