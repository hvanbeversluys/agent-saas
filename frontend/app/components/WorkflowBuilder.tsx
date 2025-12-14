"use client";

import { useState, useEffect } from "react";
import AIAssistant from "./AIAssistant";

// ===== TYPES =====

interface BusinessAction {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  prompt_template: string;
  variables: string[];
  mcp_tool_name: string | null;
  mcp_tool_icon: string | null;
}

interface Agent {
  id: string;
  name: string;
  icon: string;
}

interface TriggerType {
  id: string;
  name: string;
  description: string;
  icon: string;
}

interface SchedulePreset {
  id: string;
  label: string;
  icon: string;
}

interface EventTrigger {
  id: string;
  label: string;
  icon: string;
  source: string;
}

interface TaskType {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
}

// Un "bloc" dans le workflow
interface WorkflowBlock {
  id: string;
  type: string;
  name: string;
  icon: string;
  config: Record<string, unknown>;
}

interface MCPTool {
  id: string;
  name: string;
  icon: string;
}

interface Prompt {
  id: string;
  name: string;
}

interface Workflow {
  id: string;
  name: string;
  description: string;
  agent_id: string;
  trigger_type: string;
  trigger_config: Record<string, unknown>;
  tasks: {
    id: string;
    name: string;
    task_type: string;
    order: string;
    config: Record<string, unknown>;
  }[];
  is_active: boolean;
}

interface WorkflowBuilderProps {
  agents: Agent[];
  mcpTools?: MCPTool[];
  prompts?: Prompt[];
  editingWorkflow?: Workflow | null;
  onClose: () => void;
  onSuccess: () => void;
}

// ===== COMPONENT =====

export default function WorkflowBuilder({
  agents,
  mcpTools,
  prompts,
  editingWorkflow,
  onClose,
  onSuccess,
}: WorkflowBuilderProps) {
  // Current step
  const [step, setStep] = useState<1 | 2 | 3>(1);

  // Step 1: Basic info
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [agentId, setAgentId] = useState("");

  // Step 2: Trigger
  const [triggerType, setTriggerType] = useState("manual");
  const [schedulePreset, setSchedulePreset] = useState("");
  const [eventTrigger, setEventTrigger] = useState("");

  // Step 3: Blocks (the workflow itself)
  const [blocks, setBlocks] = useState<WorkflowBlock[]>([]);
  const [showBlockPicker, setShowBlockPicker] = useState(false);

  // Data from API
  const [businessActions, setBusinessActions] = useState<BusinessAction[]>([]);
  const [taskTypes, setTaskTypes] = useState<TaskType[]>([]);
  const [triggerTypes, setTriggerTypes] = useState<TriggerType[]>([]);
  const [schedulePresets, setSchedulePresets] = useState<SchedulePreset[]>([]);
  const [eventTriggers, setEventTriggers] = useState<EventTrigger[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Fetch data on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [actionsRes, typesRes] = await Promise.all([
          fetch(`${apiUrl}/api/business-actions`),
          fetch(`${apiUrl}/api/workflow-task-types`),
        ]);

        const actions = await actionsRes.json();
        const types = await typesRes.json();

        setBusinessActions(actions);
        setTaskTypes(types.task_types || []);
        setTriggerTypes(types.trigger_types || []);
        setSchedulePresets(types.schedule_presets || []);
        setEventTriggers(types.event_triggers || []);
      } catch (err) {
        console.error("Failed to fetch workflow data:", err);
      }
    };
    fetchData();
  }, [apiUrl]);

  // Add a block
  const addBlock = (type: string, actionId?: string) => {
    let blockName = "";
    let blockIcon = "⚡";
    const config: Record<string, unknown> = {};

    if (type === "business_action" && actionId) {
      const action = businessActions.find((a) => a.id === actionId);
      blockName = action?.name || "Action";
      blockIcon = action?.icon || "⚡";
      config.action_id = actionId;
    } else {
      const taskType = taskTypes.find((t) => t.id === type);
      blockName = taskType?.name.replace(/^\S+\s/, "") || type;
      blockIcon = taskType?.icon || "⚡";
    }

    const newBlock: WorkflowBlock = {
      id: `block-${Date.now()}`,
      type,
      name: blockName,
      icon: blockIcon,
      config,
    };

    setBlocks([...blocks, newBlock]);
    setShowBlockPicker(false);
  };

  // Remove a block
  const removeBlock = (blockId: string) => {
    setBlocks(blocks.filter((b) => b.id !== blockId));
  };

  // Submit
  const handleSubmit = async () => {
    setLoading(true);
    setError(null);

    try {
      // Convert schedule preset to cron
      const cronMap: Record<string, string> = {
        daily_morning: "0 9 * * *",
        daily_evening: "0 18 * * *",
        weekdays_morning: "0 9 * * 1-5",
        weekly_monday: "0 9 * * 1",
        monthly_first: "0 8 1 * *",
        hourly: "0 * * * *",
      };

      const triggerConfig: Record<string, unknown> = {};
      if (triggerType === "scheduled" && schedulePreset) {
        triggerConfig.cron = cronMap[schedulePreset] || "0 9 * * *";
        triggerConfig.preset = schedulePreset;
      } else if (triggerType === "event" && eventTrigger) {
        triggerConfig.event = eventTrigger;
      }

      // Convert blocks to tasks
      const tasks = blocks.map((block, idx) => ({
        id: block.id,
        name: block.name,
        description: "",
        order: String(idx + 1),
        task_type: block.type,
        config: block.config,
        on_error: "stop",
        retry_count: "0",
      }));

      const payload = {
        name,
        description,
        agent_id: agentId,
        trigger_type: triggerType,
        trigger_config: triggerConfig,
        input_schema: [],
        tasks,
        is_active: true,
      };

      const response = await fetch(`${apiUrl}/api/workflows`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) throw new Error("Erreur lors de la création");

      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  };

  // Can proceed to next step?
  const canProceed = () => {
    if (step === 1) return name.trim().length > 0 && agentId.length > 0;
    if (step === 2) {
      if (triggerType === "scheduled") return schedulePreset.length > 0;
      if (triggerType === "event") return eventTrigger.length > 0;
      return true;
    }
    if (step === 3) return blocks.length > 0;
    return false;
  };

  const getBlockColor = (type: string) => {
    switch (type) {
      case "business_action": return "bg-emerald-500";
      case "condition": return "bg-amber-500";
      case "loop": return "bg-violet-500";
      case "wait": return "bg-gray-500";
      case "human_approval": return "bg-red-500";
      default: return "bg-blue-500";
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                ✨ Créer un workflow automatisé
              </h2>
              <p className="text-gray-400 text-sm mt-1">
                Automatisez vos tâches répétitives en quelques clics
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-700 rounded-lg transition text-gray-400 hover:text-white text-2xl"
            >
              ×
            </button>
          </div>

          {/* Progress steps */}
          <div className="flex items-center gap-2 mt-6">
            {[
              { num: 1, label: "Informations" },
              { num: 2, label: "Déclencheur" },
              { num: 3, label: "Étapes" },
            ].map((s, i) => (
              <div key={s.num} className="flex items-center">
                <button
                  onClick={() => setStep(s.num as 1 | 2 | 3)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition ${
                    step === s.num
                      ? "bg-blue-600 text-white"
                      : step > s.num
                      ? "bg-green-600/20 text-green-400"
                      : "bg-gray-700 text-gray-400"
                  }`}
                >
                  {step > s.num ? "✓" : s.num}
                  <span className="hidden sm:inline">{s.label}</span>
                </button>
                {i < 2 && <span className="text-gray-600 mx-1">›</span>}
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* STEP 1: Informations */}
          {step === 1 && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Nom du workflow *
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ex: Relance automatique des devis"
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Description (optionnel)
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Décrivez ce que fait ce workflow..."
                  rows={2}
                  className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Employé numérique associé *
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {agents.map((agent) => (
                    <button
                      key={agent.id}
                      onClick={() => setAgentId(agent.id)}
                      className={`p-4 rounded-lg border-2 text-left transition ${
                        agentId === agent.id
                          ? "border-blue-500 bg-blue-500/10"
                          : "border-gray-600 hover:border-gray-500"
                      }`}
                    >
                      <span className="text-2xl">{agent.icon}</span>
                      <p className="text-white font-medium mt-1">{agent.name}</p>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Trigger */}
          {step === 2 && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-3">
                  Quand ce workflow doit-il se lancer ?
                </label>
                <div className="space-y-3">
                  {triggerTypes.map((trigger) => (
                    <button
                      key={trigger.id}
                      onClick={() => setTriggerType(trigger.id)}
                      className={`w-full p-4 rounded-lg border-2 text-left transition flex items-center gap-4 ${
                        triggerType === trigger.id
                          ? "border-blue-500 bg-blue-500/10"
                          : "border-gray-600 hover:border-gray-500"
                      }`}
                    >
                      <span className="text-2xl">{trigger.icon}</span>
                      <div>
                        <p className="text-white font-medium">{trigger.name}</p>
                        <p className="text-gray-400 text-sm">{trigger.description}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Schedule presets */}
              {triggerType === "scheduled" && (
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-3">
                    Choisissez la fréquence
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    {schedulePresets.map((preset) => (
                      <button
                        key={preset.id}
                        onClick={() => setSchedulePreset(preset.id)}
                        className={`p-3 rounded-lg border-2 text-left transition flex items-center gap-3 ${
                          schedulePreset === preset.id
                            ? "border-blue-500 bg-blue-500/10"
                            : "border-gray-600 hover:border-gray-500"
                        }`}
                      >
                        <span className="text-xl">{preset.icon}</span>
                        <span className="text-white text-sm">{preset.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Event triggers */}
              {triggerType === "event" && (
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-3">
                    Quel événement déclenche le workflow ?
                  </label>
                  <div className="space-y-2">
                    {eventTriggers.map((evt) => (
                      <button
                        key={evt.id}
                        onClick={() => setEventTrigger(evt.id)}
                        className={`w-full p-3 rounded-lg border-2 text-left transition flex items-center gap-3 ${
                          eventTrigger === evt.id
                            ? "border-blue-500 bg-blue-500/10"
                            : "border-gray-600 hover:border-gray-500"
                        }`}
                      >
                        <span className="text-xl">{evt.icon}</span>
                        <div className="flex-1">
                          <span className="text-white text-sm">{evt.label}</span>
                          <span className="text-gray-500 text-xs ml-2">
                            via {evt.source}
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* STEP 3: Build workflow */}
          {step === 3 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-gray-300">
                  Construisez votre workflow étape par étape
                </label>
              </div>

              {/* Workflow blocks */}
              <div className="space-y-3">
                {/* Start node */}
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-green-600 flex items-center justify-center text-lg">
                    ▶️
                  </div>
                  <span className="text-gray-400 text-sm">Début</span>
                </div>

                {/* Blocks */}
                {blocks.map((block, idx) => (
                  <div key={block.id} className="flex items-start gap-3">
                    {/* Connector line */}
                    <div className="w-10 flex flex-col items-center">
                      <div className="w-0.5 h-4 bg-gray-600" />
                      <div
                        className={`w-10 h-10 rounded-lg ${getBlockColor(block.type)} flex items-center justify-center text-lg`}
                      >
                        {block.icon}
                      </div>
                      {idx < blocks.length - 1 && (
                        <div className="w-0.5 h-4 bg-gray-600" />
                      )}
                    </div>

                    {/* Block card */}
                    <div className="flex-1 bg-gray-800 rounded-lg p-3 border border-gray-700 group">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-white font-medium text-sm">
                            {block.name}
                          </span>
                          {block.type === "business_action" && block.config.action_id && (
                            <span className="text-xs bg-emerald-600/20 text-emerald-400 px-2 py-0.5 rounded">
                              {businessActions.find(
                                (a) => a.id === block.config.action_id
                              )?.mcp_tool_icon || "⚡"}{" "}
                              {businessActions.find(
                                (a) => a.id === block.config.action_id
                              )?.mcp_tool_name}
                            </span>
                          )}
                        </div>
                        <button
                          onClick={() => removeBlock(block.id)}
                          className="p-1 hover:bg-gray-700 rounded opacity-0 group-hover:opacity-100 transition text-red-400"
                        >
                          🗑️
                        </button>
                      </div>
                    </div>
                  </div>
                ))}

                {/* Add block button */}
                <div className="flex items-center gap-3">
                  <div className="w-10 flex flex-col items-center">
                    {blocks.length > 0 && <div className="w-0.5 h-4 bg-gray-600" />}
                    <button
                      onClick={() => setShowBlockPicker(true)}
                      className="w-10 h-10 rounded-lg border-2 border-dashed border-gray-600 hover:border-blue-500 flex items-center justify-center transition text-gray-400 hover:text-blue-400 text-xl"
                    >
                      +
                    </button>
                  </div>
                  <button
                    onClick={() => setShowBlockPicker(true)}
                    className="text-gray-400 hover:text-white text-sm transition"
                  >
                    Ajouter une étape
                  </button>
                </div>
              </div>

              {/* Block picker modal */}
              {showBlockPicker && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                  <div className="bg-gray-800 rounded-xl p-6 max-w-xl w-full max-h-[80vh] overflow-y-auto">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-bold text-white">
                        Ajouter une étape
                      </h3>
                      <button
                        onClick={() => setShowBlockPicker(false)}
                        className="p-2 hover:bg-gray-700 rounded-lg text-gray-400 text-xl"
                      >
                        ×
                      </button>
                    </div>

                    {/* Business Actions */}
                    <div className="mb-6">
                      <h4 className="text-sm font-medium text-gray-400 mb-3">
                        ⚡ Actions Métier
                      </h4>
                      <div className="grid gap-2">
                        {businessActions.map((action) => (
                          <button
                            key={action.id}
                            onClick={() => addBlock("business_action", action.id)}
                            className="w-full p-3 rounded-lg bg-gray-700/50 hover:bg-emerald-600/20 border border-transparent hover:border-emerald-500/50 text-left transition"
                          >
                            <div className="flex items-center gap-3">
                              <span className="text-xl">{action.icon}</span>
                              <div className="flex-1 min-w-0">
                                <p className="text-white font-medium text-sm truncate">
                                  {action.name}
                                </p>
                                <p className="text-gray-400 text-xs truncate">
                                  {action.description}
                                </p>
                              </div>
                              {action.mcp_tool_icon && (
                                <span className="text-xs bg-gray-600 px-2 py-1 rounded text-gray-300">
                                  {action.mcp_tool_icon} {action.mcp_tool_name}
                                </span>
                              )}
                            </div>
                          </button>
                        ))}
                        {businessActions.length === 0 && (
                          <p className="text-gray-500 text-sm text-center py-4">
                            Aucune action métier configurée.
                            <br />
                            Créez des prompts liés à des outils MCP.
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Control blocks */}
                    <div>
                      <h4 className="text-sm font-medium text-gray-400 mb-3">
                        🔀 Contrôle du flux
                      </h4>
                      <div className="grid grid-cols-2 gap-2">
                        {taskTypes
                          .filter((t) => t.id !== "business_action")
                          .map((taskType) => (
                            <button
                              key={taskType.id}
                              onClick={() => addBlock(taskType.id)}
                              className="p-3 rounded-lg bg-gray-700/50 hover:bg-gray-600/50 border border-transparent hover:border-gray-500 text-left transition"
                            >
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-lg">{taskType.icon}</span>
                                <span className="text-white font-medium text-sm">
                                  {taskType.name.replace(/^\S+\s/, "")}
                                </span>
                              </div>
                              <p className="text-gray-400 text-xs">
                                {taskType.description}
                              </p>
                            </button>
                          ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mt-4 p-3 bg-red-500/10 border border-red-500/50 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-700 flex items-center justify-between">
          <button
            onClick={() => (step > 1 ? setStep((step - 1) as 1 | 2 | 3) : onClose())}
            className="px-4 py-2 text-gray-400 hover:text-white transition"
          >
            {step > 1 ? "← Retour" : "Annuler"}
          </button>

          <button
            onClick={() => {
              if (step < 3) setStep((step + 1) as 1 | 2 | 3);
              else handleSubmit();
            }}
            disabled={!canProceed() || loading}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition flex items-center gap-2"
          >
            {loading ? (
              "Création..."
            ) : step < 3 ? (
              "Continuer →"
            ) : (
              "✓ Créer le workflow"
            )}
          </button>
        </div>

        {/* AI Assistant */}
        <AIAssistant
          context="workflow"
          currentData={{
            name,
            description,
          }}
          onSuggestion={(field, value) => {
            if (field === "name") setName(value);
            else if (field === "description") setDescription(value);
            else if (field === "trigger_type") setTriggerType(value);
          }}
        />
      </div>
    </div>
  );
}
