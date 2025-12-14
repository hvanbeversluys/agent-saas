"use client";

import { useState, useEffect } from "react";
import AIAssistant from "./AIAssistant";

interface MCPTool {
  id: string;
  name: string;
  icon: string;
  description: string;
  category: string;
  status: string;
}

interface PromptFormData {
  name: string;
  description: string;
  category: string;
  scope: "enterprise" | "business";
  template: string;
  variables: string[];
  mcp_tool_id: string | null;
}

interface CreatePromptModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  editingPrompt?: {
    id: string;
    name: string;
    description: string;
    category: string;
    scope: "enterprise" | "business";
    template: string;
    variables: string[];
    mcp_tool_id?: string | null;
  } | null;
}

const CATEGORIES = [
  { id: "general", label: "Général" },
  { id: "commercial", label: "Commercial & Ventes" },
  { id: "seo", label: "SEO & Contenu" },
  { id: "admin", label: "Administratif" },
  { id: "direction", label: "Direction & Stratégie" },
];

const SCOPES = [
  { id: "enterprise", label: "🏢 Entreprise", desc: "Templates globaux (emails, réunions...)" },
  { id: "business", label: "🎯 Métier", desc: "Templates spécifiques (SEO, prospection...)" },
];

export default function CreatePromptModal({
  isOpen,
  onClose,
  onSuccess,
  editingPrompt,
}: CreatePromptModalProps) {
  const [formData, setFormData] = useState<PromptFormData>({
    name: "",
    description: "",
    category: "general",
    scope: "business",
    template: "",
    variables: [],
    mcp_tool_id: null,
  });
  const [newVariable, setNewVariable] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mcpTools, setMcpTools] = useState<MCPTool[]>([]);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    // Charger les outils MCP
    const fetchMcpTools = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/mcp-tools`);
        const data = await res.json();
        setMcpTools(data);
      } catch (err) {
        console.error("Failed to fetch MCP tools:", err);
      }
    };
    fetchMcpTools();
  }, [apiUrl]);

  useEffect(() => {
    if (editingPrompt) {
      setFormData({
        name: editingPrompt.name,
        description: editingPrompt.description,
        category: editingPrompt.category,
        scope: editingPrompt.scope || "business",
        template: editingPrompt.template,
        variables: editingPrompt.variables || [],
        mcp_tool_id: editingPrompt.mcp_tool_id || null,
      });
    } else {
      setFormData({
        name: "",
        description: "",
        category: "general",
        scope: "business",
        template: "",
        variables: [],
        mcp_tool_id: null,
      });
    }
  }, [editingPrompt, isOpen]);

  // Détecte automatiquement les variables dans le template
  const detectVariables = (template: string) => {
    const regex = /\{(\w+)\}/g;
    const matches = [...template.matchAll(regex)];
    const detected = [...new Set(matches.map((m) => m[1]))];
    return detected;
  };

  const handleTemplateChange = (value: string) => {
    setFormData({
      ...formData,
      template: value,
      variables: detectVariables(value),
    });
  };

  const addVariable = () => {
    if (newVariable && !formData.variables.includes(newVariable)) {
      const varName = newVariable.replace(/[^a-zA-Z0-9_]/g, "_").toLowerCase();
      setFormData({
        ...formData,
        variables: [...formData.variables, varName],
        template: formData.template + ` {${varName}}`,
      });
      setNewVariable("");
    }
  };

  const removeVariable = (varToRemove: string) => {
    setFormData({
      ...formData,
      variables: formData.variables.filter((v) => v !== varToRemove),
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const url = editingPrompt
        ? `${apiUrl}/api/prompts/${editingPrompt.id}`
        : `${apiUrl}/api/prompts`;

      const res = await fetch(url, {
        method: editingPrompt ? "PUT" : "POST",
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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-700">
          <h2 className="text-xl font-bold text-white">
            {editingPrompt ? "✏️ Modifier le prompt" : "📝 Nouveau Prompt"}
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

          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Nom du prompt *
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
              placeholder="Ex: Email de prospection"
              required
            />
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
              placeholder="À quoi sert ce prompt ?"
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

          {/* Lier à un outil MCP = Créer une Action Métier */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              🔗 Lier à un outil (optionnel)
            </label>
            <p className="text-xs text-slate-500 mb-3">
              En liant ce prompt à un outil, vous créez une &quot;Action Métier&quot; réutilisable dans les workflows.
            </p>
            <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto p-2 bg-slate-900/30 rounded-lg">
              {/* Option: pas d'outil */}
              <button
                type="button"
                onClick={() => setFormData({ ...formData, mcp_tool_id: null })}
                className={`p-3 rounded-lg border text-left transition-all ${
                  formData.mcp_tool_id === null
                    ? "border-blue-500 bg-blue-500/20"
                    : "border-slate-700 bg-slate-800 hover:border-slate-600"
                }`}
              >
                <span className="text-lg">📝</span>
                <p className="text-sm text-white mt-1">Prompt seul</p>
                <p className="text-xs text-slate-500">Sans action automatique</p>
              </button>
              
              {/* Outils MCP disponibles */}
              {mcpTools
                .filter((tool) => tool.status !== "coming_soon")
                .map((tool) => (
                  <button
                    key={tool.id}
                    type="button"
                    onClick={() => setFormData({ ...formData, mcp_tool_id: tool.id })}
                    className={`p-3 rounded-lg border text-left transition-all ${
                      formData.mcp_tool_id === tool.id
                        ? "border-emerald-500 bg-emerald-500/20"
                        : "border-slate-700 bg-slate-800 hover:border-slate-600"
                    }`}
                  >
                    <span className="text-lg">{tool.icon}</span>
                    <p className="text-sm text-white mt-1 truncate">{tool.name}</p>
                    <p className="text-xs text-slate-500 truncate">{tool.description}</p>
                  </button>
                ))}
            </div>
            {formData.mcp_tool_id && (
              <div className="mt-2 flex items-center gap-2 text-emerald-400 text-sm">
                <span>✓</span>
                <span>
                  Ce prompt deviendra une Action Métier utilisable dans les workflows
                </span>
              </div>
            )}
          </div>

          {/* Template */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Template du prompt *
            </label>
            <textarea
              value={formData.template}
              onChange={(e) => handleTemplateChange(e.target.value)}
              className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500 min-h-[150px] font-mono text-sm"
              placeholder="Rédige un email de prospection pour {nom_entreprise}...

Les variables sont automatiquement détectées avec la syntaxe {variable}."
              required
            />
            <p className="text-xs text-slate-500 mt-1">
              Utilisez <code className="bg-slate-700 px-1 rounded">{"{variable}"}</code> pour créer des champs dynamiques.
            </p>
          </div>

          {/* Variables */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Variables détectées
            </label>
            <div className="flex flex-wrap gap-2 p-3 bg-slate-900/50 rounded-lg min-h-[50px]">
              {formData.variables.length === 0 ? (
                <span className="text-slate-500 text-sm">
                  Aucune variable. Utilisez {"{nom}"} dans le template.
                </span>
              ) : (
                formData.variables.map((variable) => (
                  <span
                    key={variable}
                    className="flex items-center gap-1 bg-blue-600/30 text-blue-300 px-2 py-1 rounded text-sm"
                  >
                    {"{"}
                    {variable}
                    {"}"}
                    <button
                      type="button"
                      onClick={() => removeVariable(variable)}
                      className="hover:text-red-400 ml-1"
                    >
                      ×
                    </button>
                  </span>
                ))
              )}
            </div>

            {/* Add custom variable */}
            <div className="flex gap-2 mt-2">
              <input
                type="text"
                value={newVariable}
                onChange={(e) => setNewVariable(e.target.value)}
                className="flex-1 bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500"
                placeholder="Ajouter une variable..."
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addVariable())}
              />
              <button
                type="button"
                onClick={addVariable}
                className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm"
              >
                + Ajouter
              </button>
            </div>
          </div>

          {/* Preview */}
          {formData.template && (
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">
                👁️ Aperçu
              </label>
              <div className="p-4 bg-slate-900/50 border border-slate-600 rounded-lg">
                <p className="text-slate-300 text-sm whitespace-pre-wrap">
                  {formData.template.replace(
                    /\{(\w+)\}/g,
                    (_, varName) => `[${varName}]`
                  )}
                </p>
              </div>
            </div>
          )}

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
              {loading ? "Enregistrement..." : editingPrompt ? "Mettre à jour" : "Créer le prompt"}
            </button>
          </div>
        </form>

        {/* AI Assistant */}
        <AIAssistant
          context="prompt"
          currentData={{
            name: formData.name,
            description: formData.description,
            template: formData.template,
            category: formData.category,
          }}
          onSuggestion={(field, value) => {
            if (field === "template") {
              handleTemplateChange(value);
            } else if (field === "name") {
              setFormData({ ...formData, name: value });
            } else if (field === "description") {
              setFormData({ ...formData, description: value });
            }
          }}
        />
      </div>
    </div>
  );
}
