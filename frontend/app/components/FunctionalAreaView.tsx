"use client";

import { useState, useEffect } from "react";

interface FunctionalArea {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  order: string;
  is_active: boolean;
  agents_count: number;
  prompts_count: number;
  workflows_count: number;
  mcp_tools_count: number;
}

interface FunctionalAreaDetails {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  agents: { id: string; name: string; icon: string; description: string }[];
  prompts: { id: string; name: string; description: string; category: string }[];
  workflows: { id: string; name: string; description: string; trigger_type: string }[];
  mcp_tools: { id: string; name: string; icon: string; status: string }[];
}

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  scope: string;
  functional_area_id?: string;
}

interface Prompt {
  id: string;
  name: string;
  description: string;
  category: string;
  functional_area_id?: string;
}

interface Workflow {
  id: string;
  name: string;
  description: string;
  trigger_type: string;
  functional_area_id?: string;
}

interface FunctionalAreaViewProps {
  agents: Agent[];
  prompts: Prompt[];
  workflows: Workflow[];
  onSelectAgent?: (agentId: string) => void;
  onSelectWorkflow?: (workflowId: string) => void;
}

const colorClasses: Record<string, { bg: string; border: string; text: string; gradient: string }> = {
  purple: { bg: "bg-purple-500/10", border: "border-purple-500/30", text: "text-purple-400", gradient: "from-purple-500/20" },
  blue: { bg: "bg-blue-500/10", border: "border-blue-500/30", text: "text-blue-400", gradient: "from-blue-500/20" },
  pink: { bg: "bg-pink-500/10", border: "border-pink-500/30", text: "text-pink-400", gradient: "from-pink-500/20" },
  amber: { bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-400", gradient: "from-amber-500/20" },
  green: { bg: "bg-green-500/10", border: "border-green-500/30", text: "text-green-400", gradient: "from-green-500/20" },
  cyan: { bg: "bg-cyan-500/10", border: "border-cyan-500/30", text: "text-cyan-400", gradient: "from-cyan-500/20" },
};

export default function FunctionalAreaView({
  agents,
  prompts,
  workflows,
  onSelectAgent,
  onSelectWorkflow,
}: FunctionalAreaViewProps) {
  const [areas, setAreas] = useState<FunctionalArea[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedArea, setExpandedArea] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    fetch(`${apiUrl}/api/functional-areas`)
      .then((res) => res.json())
      .then((data) => {
        setAreas(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error fetching functional areas:", err);
        setLoading(false);
      });
  }, [apiUrl]);

  // Grouper les éléments par périmètre
  const groupedAgents = agents.reduce((acc, agent) => {
    const areaId = agent.functional_area_id || "unassigned";
    if (!acc[areaId]) acc[areaId] = [];
    acc[areaId].push(agent);
    return acc;
  }, {} as Record<string, Agent[]>);

  const groupedPrompts = prompts.reduce((acc, prompt) => {
    const areaId = prompt.functional_area_id || "unassigned";
    if (!acc[areaId]) acc[areaId] = [];
    acc[areaId].push(prompt);
    return acc;
  }, {} as Record<string, Prompt[]>);

  const groupedWorkflows = workflows.reduce((acc, workflow) => {
    const areaId = workflow.functional_area_id || "unassigned";
    if (!acc[areaId]) acc[areaId] = [];
    acc[areaId].push(workflow);
    return acc;
  }, {} as Record<string, Workflow[]>);

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 bg-gray-800 rounded-xl" />
        ))}
      </div>
    );
  }

  const triggerLabels: Record<string, string> = {
    manual: "🖱️ Manuel",
    cron: "⏰ Planifié",
    event: "⚡ Événement",
  };

  return (
    <div className="space-y-4">
      {areas.map((area) => {
        const colors = colorClasses[area.color] || colorClasses.blue;
        const areaAgents = groupedAgents[area.id] || [];
        const areaPrompts = groupedPrompts[area.id] || [];
        const areaWorkflows = groupedWorkflows[area.id] || [];
        const isExpanded = expandedArea === area.id;
        const totalItems = areaAgents.length + areaPrompts.length + areaWorkflows.length;

        if (totalItems === 0) return null;

        return (
          <div
            key={area.id}
            className={`rounded-xl border ${colors.border} overflow-hidden`}
          >
            {/* Header */}
            <button
              onClick={() => setExpandedArea(isExpanded ? null : area.id)}
              className={`w-full p-4 flex items-center justify-between bg-gradient-to-r ${colors.gradient} to-transparent hover:bg-gray-800/50 transition-colors`}
            >
              <div className="flex items-center gap-3">
                <span className="text-2xl">{area.icon}</span>
                <div className="text-left">
                  <h3 className={`font-semibold ${colors.text}`}>{area.name}</h3>
                  <p className="text-sm text-gray-500">{area.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex gap-3 text-sm text-gray-400">
                  {areaAgents.length > 0 && (
                    <span>🤖 {areaAgents.length}</span>
                  )}
                  {areaPrompts.length > 0 && (
                    <span>📝 {areaPrompts.length}</span>
                  )}
                  {areaWorkflows.length > 0 && (
                    <span>⚡ {areaWorkflows.length}</span>
                  )}
                </div>
                <span className={`text-xl transition-transform ${isExpanded ? "rotate-180" : ""}`}>
                  ▼
                </span>
              </div>
            </button>

            {/* Content */}
            {isExpanded && (
              <div className="p-4 bg-gray-900/50 space-y-4">
                {/* Agents */}
                {areaAgents.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-400 mb-2 flex items-center gap-2">
                      <span>🤖</span> Agents ({areaAgents.length})
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                      {areaAgents.map((agent) => (
                        <button
                          key={agent.id}
                          onClick={() => onSelectAgent?.(agent.id)}
                          className="p-3 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors text-left"
                        >
                          <div className="flex items-center gap-2">
                            <span className="text-xl">{agent.icon}</span>
                            <div>
                              <div className="font-medium text-white text-sm">{agent.name}</div>
                              <div className="text-xs text-gray-500 line-clamp-1">{agent.description}</div>
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Prompts */}
                {areaPrompts.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-400 mb-2 flex items-center gap-2">
                      <span>📝</span> Prompts ({areaPrompts.length})
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {areaPrompts.map((prompt) => (
                        <span
                          key={prompt.id}
                          className="px-3 py-1.5 bg-gray-800 rounded-lg text-sm text-gray-300"
                        >
                          {prompt.name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Workflows */}
                {areaWorkflows.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-400 mb-2 flex items-center gap-2">
                      <span>⚡</span> Workflows ({areaWorkflows.length})
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {areaWorkflows.map((workflow) => (
                        <button
                          key={workflow.id}
                          onClick={() => onSelectWorkflow?.(workflow.id)}
                          className="p-3 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors text-left flex items-center justify-between"
                        >
                          <div>
                            <div className="font-medium text-white text-sm">{workflow.name}</div>
                            <div className="text-xs text-gray-500 line-clamp-1">{workflow.description}</div>
                          </div>
                          <span className="text-xs bg-gray-700 px-2 py-1 rounded">
                            {triggerLabels[workflow.trigger_type] || workflow.trigger_type}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}

      {/* Éléments non assignés */}
      {(groupedAgents["unassigned"]?.length > 0 ||
        groupedPrompts["unassigned"]?.length > 0 ||
        groupedWorkflows["unassigned"]?.length > 0) && (
        <div className="rounded-xl border border-gray-700 overflow-hidden">
          <button
            onClick={() => setExpandedArea(expandedArea === "unassigned" ? null : "unassigned")}
            className="w-full p-4 flex items-center justify-between bg-gray-800/30 hover:bg-gray-800/50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="text-2xl">📦</span>
              <div className="text-left">
                <h3 className="font-semibold text-gray-400">Non classés</h3>
                <p className="text-sm text-gray-500">Éléments sans périmètre assigné</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex gap-3 text-sm text-gray-500">
                {groupedAgents["unassigned"]?.length > 0 && (
                  <span>🤖 {groupedAgents["unassigned"].length}</span>
                )}
                {groupedPrompts["unassigned"]?.length > 0 && (
                  <span>📝 {groupedPrompts["unassigned"].length}</span>
                )}
                {groupedWorkflows["unassigned"]?.length > 0 && (
                  <span>⚡ {groupedWorkflows["unassigned"].length}</span>
                )}
              </div>
              <span className={`text-xl transition-transform ${expandedArea === "unassigned" ? "rotate-180" : ""}`}>
                ▼
              </span>
            </div>
          </button>

          {expandedArea === "unassigned" && (
            <div className="p-4 bg-gray-900/50 space-y-4">
              {groupedAgents["unassigned"]?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-400 mb-2">🤖 Agents</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {groupedAgents["unassigned"].map((agent) => (
                      <button
                        key={agent.id}
                        onClick={() => onSelectAgent?.(agent.id)}
                        className="p-3 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors text-left"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-xl">{agent.icon}</span>
                          <div>
                            <div className="font-medium text-white text-sm">{agent.name}</div>
                            <div className="text-xs text-gray-500 line-clamp-1">{agent.description}</div>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {groupedWorkflows["unassigned"]?.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-400 mb-2">⚡ Workflows</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {groupedWorkflows["unassigned"].map((workflow) => (
                      <button
                        key={workflow.id}
                        onClick={() => onSelectWorkflow?.(workflow.id)}
                        className="p-3 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors text-left"
                      >
                        <div className="font-medium text-white text-sm">{workflow.name}</div>
                        <div className="text-xs text-gray-500">{workflow.description}</div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
