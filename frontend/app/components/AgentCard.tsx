"use client";

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  scope?: "enterprise" | "business";
  system_prompt: string;
  mcp_tools: { id: string; name: string; icon: string }[];
  prompts: { id: string; name: string }[];
  is_active: boolean;
}

interface AgentCardProps {
  agent: Agent;
  isSelected: boolean;
  onSelect: (agent: Agent) => void;
  onEdit?: () => void;
  onDelete?: () => void;
}

export default function AgentCard({ agent, isSelected, onSelect, onEdit, onDelete }: AgentCardProps) {
  const toolsCount = Array.isArray(agent.mcp_tools) ? agent.mcp_tools.length : 0;
  const promptsCount = agent.prompts?.length || 0;
  const scope = agent.scope || "business";

  return (
    <div
      className={`relative p-4 rounded-xl border transition-all duration-200 ${
        isSelected
          ? scope === "enterprise"
            ? "bg-purple-600/20 border-purple-500 shadow-lg shadow-purple-500/20"
            : "bg-amber-600/20 border-amber-500 shadow-lg shadow-amber-500/20"
          : "bg-slate-800/50 border-slate-700 hover:border-slate-600 hover:bg-slate-800"
      }`}
    >
      {/* Edit/Delete buttons */}
      {(onEdit || onDelete) && (
        <div className="absolute top-2 right-2 flex gap-1 opacity-0 hover:opacity-100 transition-opacity group-hover:opacity-100">
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
        onClick={() => onSelect(agent)}
        className="w-full text-left"
      >
        <div className="flex items-start gap-3">
          <span className="text-2xl">{agent.icon}</span>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-white truncate">{agent.name}</h3>
            <p className="text-sm text-slate-400 line-clamp-2 mt-1">
              {agent.description}
            </p>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                scope === "enterprise"
                  ? "bg-purple-500/20 text-purple-300"
                  : "bg-amber-500/20 text-amber-300"
              }`}>
                {scope === "enterprise" ? "🏢" : "🎯"}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                agent.is_active 
                  ? "bg-green-500/20 text-green-400" 
                  : "bg-slate-600/50 text-slate-400"
              }`}>
                {agent.is_active ? "Actif" : "Inactif"}
              </span>
              <span className="text-xs text-slate-500">
                🔌 {toolsCount}
              </span>
              <span className="text-xs text-slate-500">
                📝 {promptsCount}
              </span>
            </div>
          </div>
        </div>
      </button>
    </div>
  );
}
