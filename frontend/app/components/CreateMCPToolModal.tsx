"use client";

import { useState, useEffect } from "react";

interface MCPToolFormData {
  name: string;
  description: string;
  icon: string;
  category: string;
  scope: "enterprise" | "business";
  status: string;
  config_required: string[];
}

interface CreateMCPToolModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  editingTool?: {
    id: string;
    name: string;
    description: string;
    icon: string;
    category: string;
    scope: "enterprise" | "business";
    status: string;
    config_required: string[];
  } | null;
}

const ICONS = ["🔌", "📧", "👥", "📄", "📅", "🔍", "📊", "🧾", "✅", "💼", "📞", "🌐", "💾", "🔗", "⚙️"];
const CATEGORIES = [
  { id: "general", label: "Général" },
  { id: "email", label: "Email" },
  { id: "crm", label: "CRM & Contacts" },
  { id: "seo", label: "SEO & Analytics" },
  { id: "facturation", label: "Facturation" },
  { id: "productivity", label: "Productivité" },
  { id: "communication", label: "Communication" },
];
const STATUSES = [
  { id: "active", label: "✅ Actif", description: "Prêt à l'emploi" },
  { id: "beta", label: "🧪 Beta", description: "En test" },
  { id: "coming_soon", label: "🔜 Bientôt", description: "En développement" },
  { id: "disabled", label: "⛔ Désactivé", description: "Non disponible" },
];
const SCOPES = [
  { id: "enterprise", label: "🏢 Entreprise", desc: "Outils globaux (CRM, Email, Calendar...)" },
  { id: "business", label: "🎯 Métier", desc: "Outils spécifiques (SEO, Facturation...)" },
];

export default function CreateMCPToolModal({
  isOpen,
  onClose,
  onSuccess,
  editingTool,
}: CreateMCPToolModalProps) {
  const [formData, setFormData] = useState<MCPToolFormData>({
    name: "",
    description: "",
    icon: "🔌",
    category: "general",
    scope: "business",
    status: "active",
    config_required: [],
  });
  const [newConfig, setNewConfig] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    if (editingTool) {
      setFormData({
        name: editingTool.name,
        description: editingTool.description,
        icon: editingTool.icon,
        category: editingTool.category,
        scope: editingTool.scope || "business",
        status: editingTool.status,
        config_required: editingTool.config_required || [],
      });
    } else {
      setFormData({
        name: "",
        description: "",
        icon: "🔌",
        category: "general",
        scope: "business",
        status: "active",
        config_required: [],
      });
    }
  }, [editingTool, isOpen]);

  const addConfigKey = () => {
    if (newConfig && !formData.config_required.includes(newConfig)) {
      const key = newConfig.replace(/[^a-zA-Z0-9_]/g, "_").toLowerCase();
      setFormData({
        ...formData,
        config_required: [...formData.config_required, key],
      });
      setNewConfig("");
    }
  };

  const removeConfigKey = (keyToRemove: string) => {
    setFormData({
      ...formData,
      config_required: formData.config_required.filter((k) => k !== keyToRemove),
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const url = editingTool
        ? `${apiUrl}/api/mcp-tools/${editingTool.id}`
        : `${apiUrl}/api/mcp-tools`;

      const res = await fetch(url, {
        method: editingTool ? "PUT" : "POST",
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
            {editingTool ? "✏️ Modifier l'outil MCP" : "🔌 Nouvel Outil MCP"}
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
                Nom de l&apos;outil *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                placeholder="Ex: Google Drive Connector"
                required
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 min-h-[80px]"
              placeholder="Que fait cet outil ? Quels services connecte-t-il ?"
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

          {/* Category & Status */}
          <div className="grid grid-cols-2 gap-4">
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
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">
                Statut
              </label>
              <select
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
              >
                {STATUSES.map((status) => (
                  <option key={status.id} value={status.id}>
                    {status.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Config Required */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              ⚙️ Configuration requise
            </label>
            <p className="text-xs text-slate-500 mb-2">
              Définissez les clés de configuration que l&apos;utilisateur devra renseigner (API keys, tokens...).
            </p>
            <div className="flex flex-wrap gap-2 p-3 bg-slate-900/50 rounded-lg min-h-[50px]">
              {formData.config_required.length === 0 ? (
                <span className="text-slate-500 text-sm">
                  Aucune configuration requise
                </span>
              ) : (
                formData.config_required.map((key) => (
                  <span
                    key={key}
                    className="flex items-center gap-1 bg-amber-600/30 text-amber-300 px-2 py-1 rounded text-sm"
                  >
                    🔑 {key}
                    <button
                      type="button"
                      onClick={() => removeConfigKey(key)}
                      className="hover:text-red-400 ml-1"
                    >
                      ×
                    </button>
                  </span>
                ))
              )}
            </div>

            {/* Add config key */}
            <div className="flex gap-2 mt-2">
              <input
                type="text"
                value={newConfig}
                onChange={(e) => setNewConfig(e.target.value)}
                className="flex-1 bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500"
                placeholder="Ex: api_key, oauth_token..."
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addConfigKey())}
              />
              <button
                type="button"
                onClick={addConfigKey}
                className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm"
              >
                + Ajouter
              </button>
            </div>
          </div>

          {/* MCP Info */}
          <div className="bg-slate-900/50 border border-slate-600 rounded-lg p-4">
            <h4 className="text-sm font-medium text-slate-300 mb-2">ℹ️ À propos des outils MCP</h4>
            <p className="text-xs text-slate-500">
              Les outils MCP (Model Context Protocol) permettent aux agents de se connecter à des services externes. 
              En production, chaque outil sera lié à un serveur MCP réel via SSE.
            </p>
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
              {loading ? "Enregistrement..." : editingTool ? "Mettre à jour" : "Créer l'outil"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
