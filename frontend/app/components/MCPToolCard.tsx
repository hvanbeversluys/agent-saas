"use client";

interface MCPTool {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  scope?: "enterprise" | "business";
  status: string;
  config_required: string[];
}

interface MCPToolCardProps {
  tool: MCPTool;
  onConfigure?: (tool: MCPTool) => void;
  onEdit?: () => void;
  onDelete?: () => void;
}

export default function MCPToolCard({ tool, onConfigure, onEdit, onDelete }: MCPToolCardProps) {
  const scope = tool.scope || "business";
  const statusConfig = {
    active: { label: "Actif", color: "bg-green-500/20 text-green-400", dot: "bg-green-400" },
    beta: { label: "Beta", color: "bg-amber-500/20 text-amber-400", dot: "bg-amber-400" },
    coming_soon: { label: "Bientôt", color: "bg-slate-600/50 text-slate-400", dot: "bg-slate-400" },
  };

  const status = statusConfig[tool.status as keyof typeof statusConfig] || statusConfig.coming_soon;

  return (
    <div className={`bg-slate-800/50 border border-slate-700 rounded-xl p-4 transition-all relative group ${
      tool.status === "coming_soon" ? "opacity-60" : "hover:border-slate-600"
    }`}>
      {/* Edit/Delete buttons */}
      {(onEdit || onDelete) && (
        <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
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

      <div className="flex items-start gap-3">
        <span className="text-2xl">{tool.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-white">{tool.name}</h3>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              scope === "enterprise"
                ? "bg-purple-500/20 text-purple-300"
                : "bg-amber-500/20 text-amber-300"
            }`}>
              {scope === "enterprise" ? "🏢" : "🎯"}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full flex items-center gap-1 ${status.color}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${status.dot}`}></span>
              {status.label}
            </span>
          </div>
          <p className="text-sm text-slate-400 line-clamp-2">{tool.description}</p>
          
          {tool.status !== "coming_soon" && (
            <button
              onClick={() => onConfigure?.(tool)}
              className="mt-3 text-sm text-blue-400 hover:text-blue-300 transition-colors"
            >
              ⚙️ Configurer
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
