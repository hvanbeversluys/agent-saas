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

interface FunctionalAreaSelectorProps {
  selectedAreaId: string | null;
  onSelect: (areaId: string | null) => void;
  showCounts?: boolean;
  compact?: boolean;
}

const colorClasses: Record<string, { bg: string; border: string; text: string }> = {
  purple: { bg: "bg-purple-500/20", border: "border-purple-500", text: "text-purple-400" },
  blue: { bg: "bg-blue-500/20", border: "border-blue-500", text: "text-blue-400" },
  pink: { bg: "bg-pink-500/20", border: "border-pink-500", text: "text-pink-400" },
  amber: { bg: "bg-amber-500/20", border: "border-amber-500", text: "text-amber-400" },
  green: { bg: "bg-green-500/20", border: "border-green-500", text: "text-green-400" },
  cyan: { bg: "bg-cyan-500/20", border: "border-cyan-500", text: "text-cyan-400" },
};

export default function FunctionalAreaSelector({
  selectedAreaId,
  onSelect,
  showCounts = true,
  compact = false,
}: FunctionalAreaSelectorProps) {
  const [areas, setAreas] = useState<FunctionalArea[]>([]);
  const [loading, setLoading] = useState(true);

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

  if (loading) {
    return (
      <div className="flex gap-2 animate-pulse">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-10 w-32 bg-gray-700 rounded-lg" />
        ))}
      </div>
    );
  }

  if (compact) {
    return (
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => onSelect(null)}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
            selectedAreaId === null
              ? "bg-white text-gray-900"
              : "bg-gray-800 text-gray-400 hover:bg-gray-700"
          }`}
        >
          Tous
        </button>
        {areas.map((area) => {
          const colors = colorClasses[area.color] || colorClasses.blue;
          const isSelected = selectedAreaId === area.id;
          return (
            <button
              key={area.id}
              onClick={() => onSelect(area.id)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 ${
                isSelected
                  ? `${colors.bg} ${colors.border} border ${colors.text}`
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}
            >
              <span>{area.icon}</span>
              <span>{area.name}</span>
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {/* Option "Tous" */}
      <button
        onClick={() => onSelect(null)}
        className={`p-4 rounded-xl border-2 transition-all ${
          selectedAreaId === null
            ? "bg-white/10 border-white text-white"
            : "bg-gray-800/50 border-gray-700 text-gray-400 hover:border-gray-500"
        }`}
      >
        <div className="text-2xl mb-2">🏢</div>
        <div className="font-semibold text-sm">Tous les périmètres</div>
        {showCounts && (
          <div className="text-xs mt-1 opacity-70">
            {areas.reduce((sum, a) => sum + a.agents_count, 0)} agents
          </div>
        )}
      </button>

      {areas.map((area) => {
        const colors = colorClasses[area.color] || colorClasses.blue;
        const isSelected = selectedAreaId === area.id;
        const totalItems = area.agents_count + area.prompts_count + area.workflows_count;

        return (
          <button
            key={area.id}
            onClick={() => onSelect(area.id)}
            className={`p-4 rounded-xl border-2 transition-all text-left ${
              isSelected
                ? `${colors.bg} ${colors.border} ${colors.text}`
                : "bg-gray-800/50 border-gray-700 text-gray-400 hover:border-gray-500"
            }`}
          >
            <div className="text-2xl mb-2">{area.icon}</div>
            <div className="font-semibold text-sm">{area.name}</div>
            {showCounts && (
              <div className="text-xs mt-1 opacity-70">
                {area.agents_count} agents · {area.workflows_count} workflows
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}
