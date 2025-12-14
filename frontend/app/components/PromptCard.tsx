"use client";

import { useState } from "react";

interface Prompt {
  id: string;
  name: string;
  description: string;
  category: string;
  scope?: "enterprise" | "business";
  template: string;
  variables: string[];
}

interface PromptCardProps {
  prompt: Prompt;
  onUse: (prompt: Prompt, filledTemplate: string) => void;
  onEdit?: () => void;
  onDelete?: () => void;
}

export default function PromptCard({ prompt, onUse, onEdit, onDelete }: PromptCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [variables, setVariables] = useState<Record<string, string>>({});
  const scope = prompt.scope || "business";

  const handleVariableChange = (variable: string, value: string) => {
    setVariables((prev) => ({ ...prev, [variable]: value }));
  };

  const generateFilledTemplate = () => {
    let filled = prompt.template;
    prompt.variables.forEach((v) => {
      const value = variables[v] || `[${v}]`;
      filled = filled.replace(new RegExp(`\\{${v}\\}`, "g"), value);
    });
    return filled;
  };

  const handleUse = () => {
    const filled = generateFilledTemplate();
    onUse(prompt, filled);
  };

  const categoryColors: Record<string, string> = {
    commercial: "bg-purple-500/20 text-purple-400",
    seo: "bg-green-500/20 text-green-400",
    admin: "bg-blue-500/20 text-blue-400",
    direction: "bg-amber-500/20 text-amber-400",
  };

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden relative group">
      {/* Edit/Delete buttons */}
      {(onEdit || onDelete) && (
        <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
          {onEdit && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onEdit();
              }}
              className="p-1.5 bg-slate-700 hover:bg-blue-600 rounded text-xs"
              title="Modifier"
            >
              ✏️
            </button>
          )}
          {onDelete && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
              className="p-1.5 bg-slate-700 hover:bg-red-600 rounded text-xs"
              title="Supprimer"
            >
              🗑️
            </button>
          )}
        </div>
      )}

      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 text-left hover:bg-slate-800/80 transition-colors"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-white">{prompt.name}</h3>
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                scope === "enterprise"
                  ? "bg-purple-500/20 text-purple-300"
                  : "bg-amber-500/20 text-amber-300"
              }`}>
                {scope === "enterprise" ? "🏢" : "🎯"}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full ${categoryColors[prompt.category] || "bg-slate-600 text-slate-300"}`}>
                {prompt.category}
              </span>
            </div>
            <p className="text-sm text-slate-400">{prompt.description}</p>
          </div>
          <span className={`text-slate-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}>
            ▼
          </span>
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 border-t border-slate-700/50">
          <div className="mt-4 space-y-3">
            <h4 className="text-sm font-medium text-slate-300">Variables à remplir:</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {prompt.variables.map((variable) => (
                <div key={variable}>
                  <label className="block text-xs text-slate-400 mb-1">
                    {variable.replace(/_/g, " ")}
                  </label>
                  <input
                    type="text"
                    value={variables[variable] || ""}
                    onChange={(e) => handleVariableChange(variable, e.target.value)}
                    placeholder={`Entrez ${variable.replace(/_/g, " ")}`}
                    className="w-full px-3 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4">
            <h4 className="text-sm font-medium text-slate-300 mb-2">Aperçu:</h4>
            <div className="bg-slate-900/50 rounded-lg p-3 max-h-48 overflow-y-auto">
              <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono">
                {generateFilledTemplate()}
              </pre>
            </div>
          </div>

          <button
            onClick={handleUse}
            className="mt-4 w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            Utiliser ce prompt
          </button>
        </div>
      )}
    </div>
  );
}
