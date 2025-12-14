"use client";

import { useState } from "react";
import AIAssistant from "./AIAssistant";

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

interface EmployeeWizardProps {
  mcpTools: MCPTool[];
  prompts: Prompt[];
  onClose: () => void;
  onSuccess: () => void;
}

type WizardStep = "identity" | "role" | "tools" | "prompts" | "review";

const ICONS = ["🤖", "👨‍💼", "👩‍💻", "🧑‍🔧", "👨‍🎨", "👩‍🔬", "🧑‍💼", "👨‍✈️", "🦸", "🧙", "🎯", "⚡", "🚀", "💡", "📊"];

const CATEGORIES = [
  { id: "support", name: "Support Client", icon: "🎧", description: "Répondre aux questions des clients" },
  { id: "sales", name: "Commercial", icon: "💼", description: "Prospection et suivi commercial" },
  { id: "content", name: "Rédaction", icon: "✍️", description: "Création de contenu et copywriting" },
  { id: "analysis", name: "Analyse", icon: "📊", description: "Analyse de données et reporting" },
  { id: "dev", name: "Technique", icon: "💻", description: "Assistance technique et développement" },
  { id: "admin", name: "Administratif", icon: "📁", description: "Tâches administratives et organisation" },
];

export default function EmployeeWizard({ mcpTools, prompts, onClose, onSuccess }: EmployeeWizardProps) {
  const [step, setStep] = useState<WizardStep>("identity");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form data
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState("🤖");
  const [category, setCategory] = useState("");
  const [scope, setScope] = useState<"enterprise" | "business">("business");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [selectedPrompts, setSelectedPrompts] = useState<string[]>([]);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const steps: { id: WizardStep; title: string; icon: string }[] = [
    { id: "identity", title: "Identité", icon: "1" },
    { id: "role", title: "Rôle", icon: "2" },
    { id: "tools", title: "Outils", icon: "3" },
    { id: "prompts", title: "Prompts", icon: "4" },
    { id: "review", title: "Résumé", icon: "5" },
  ];

  const currentStepIndex = steps.findIndex((s) => s.id === step);

  const canProceed = () => {
    switch (step) {
      case "identity":
        return name.trim().length > 0 && description.trim().length > 0;
      case "role":
        return category.length > 0;
      case "tools":
        return true; // Tools are optional
      case "prompts":
        return true; // Prompts are optional
      case "review":
        return true;
      default:
        return false;
    }
  };

  const handleNext = () => {
    const nextStep = steps[currentStepIndex + 1];
    if (nextStep) setStep(nextStep.id);
  };

  const handleBack = () => {
    const prevStep = steps[currentStepIndex - 1];
    if (prevStep) setStep(prevStep.id);
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${apiUrl}/api/agents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          description,
          icon,
          category,
          scope,
          system_prompt: systemPrompt || `Tu es ${name}, un assistant spécialisé dans ${CATEGORIES.find(c => c.id === category)?.name || category}.`,
          mcp_tool_ids: selectedTools,
          prompt_ids: selectedPrompts,
          is_active: true,
        }),
      });

      if (!response.ok) {
        throw new Error("Erreur lors de la création");
      }

      onSuccess();
    } catch (err) {
      setError("Impossible de créer l'employé. Réessayez.");
    } finally {
      setLoading(false);
    }
  };

  const toggleTool = (toolId: string) => {
    setSelectedTools((prev) =>
      prev.includes(toolId) ? prev.filter((id) => id !== toolId) : [...prev, toolId]
    );
  };

  const togglePrompt = (promptId: string) => {
    setSelectedPrompts((prev) =>
      prev.includes(promptId) ? prev.filter((id) => id !== promptId) : [...prev, promptId]
    );
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-slate-700">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-white">✨ Créer un Employé Virtuel</h2>
            <button onClick={onClose} className="text-slate-400 hover:text-white text-xl">
              ✕
            </button>
          </div>

          {/* Progress */}
          <div className="flex items-center justify-between">
            {steps.map((s, i) => (
              <div key={s.id} className="flex items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all ${
                    i <= currentStepIndex
                      ? "bg-purple-600 text-white"
                      : "bg-slate-700 text-slate-400"
                  }`}
                >
                  {i < currentStepIndex ? "✓" : s.icon}
                </div>
                <span
                  className={`ml-2 text-sm hidden sm:block ${
                    i <= currentStepIndex ? "text-white" : "text-slate-500"
                  }`}
                >
                  {s.title}
                </span>
                {i < steps.length - 1 && (
                  <div
                    className={`w-8 sm:w-12 h-0.5 mx-2 ${
                      i < currentStepIndex ? "bg-purple-600" : "bg-slate-700"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Step: Identity */}
          {step === "identity" && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Choisir une icône
                </label>
                <div className="flex flex-wrap gap-2">
                  {ICONS.map((emoji) => (
                    <button
                      key={emoji}
                      onClick={() => setIcon(emoji)}
                      className={`w-12 h-12 text-2xl rounded-xl border-2 transition-all ${
                        icon === emoji
                          ? "border-purple-500 bg-purple-500/20"
                          : "border-slate-700 hover:border-slate-600"
                      }`}
                    >
                      {emoji}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Nom de l&apos;employé *
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ex: Sarah l'Assistante SEO"
                  className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Description courte *
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Décrivez ce que fait cet employé en une phrase..."
                  rows={2}
                  className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Portée
                </label>
                <div className="flex gap-3">
                  <button
                    onClick={() => setScope("business")}
                    className={`flex-1 p-4 rounded-xl border-2 transition-all ${
                      scope === "business"
                        ? "border-amber-500 bg-amber-500/10"
                        : "border-slate-700 hover:border-slate-600"
                    }`}
                  >
                    <span className="text-2xl mb-2 block">🎯</span>
                    <span className="font-medium text-white">Métier</span>
                    <p className="text-xs text-slate-400 mt-1">Spécifique à votre activité</p>
                  </button>
                  <button
                    onClick={() => setScope("enterprise")}
                    className={`flex-1 p-4 rounded-xl border-2 transition-all ${
                      scope === "enterprise"
                        ? "border-purple-500 bg-purple-500/10"
                        : "border-slate-700 hover:border-slate-600"
                    }`}
                  >
                    <span className="text-2xl mb-2 block">🏢</span>
                    <span className="font-medium text-white">Entreprise</span>
                    <p className="text-xs text-slate-400 mt-1">Commun à tous les services</p>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Step: Role */}
          {step === "role" && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-4">
                  Quel sera son rôle principal ?
                </label>
                <div className="grid grid-cols-2 gap-4">
                  {CATEGORIES.map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() => setCategory(cat.id)}
                      className={`p-4 rounded-xl border-2 text-left transition-all ${
                        category === cat.id
                          ? "border-purple-500 bg-purple-500/10"
                          : "border-slate-700 hover:border-slate-600"
                      }`}
                    >
                      <span className="text-3xl mb-2 block">{cat.icon}</span>
                      <span className="font-medium text-white block">{cat.name}</span>
                      <p className="text-xs text-slate-400 mt-1">{cat.description}</p>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Instructions personnalisées (optionnel)
                </label>
                <textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  placeholder="Instructions spécifiques pour cet employé... (laisser vide pour utiliser les instructions par défaut)"
                  rows={4}
                  className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 resize-none font-mono text-sm"
                />
              </div>
            </div>
          )}

          {/* Step: Tools */}
          {step === "tools" && (
            <div className="space-y-4">
              <p className="text-slate-400 text-sm mb-4">
                Sélectionnez les outils auxquels cet employé aura accès. Ces outils lui permettent d&apos;interagir avec des services externes.
              </p>
              
              {mcpTools.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {mcpTools.map((tool) => (
                    <button
                      key={tool.id}
                      onClick={() => toggleTool(tool.id)}
                      className={`p-4 rounded-xl border-2 text-left transition-all ${
                        selectedTools.includes(tool.id)
                          ? "border-blue-500 bg-blue-500/10"
                          : "border-slate-700 hover:border-slate-600"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <span className="text-2xl">{tool.icon}</span>
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-white">{tool.name}</span>
                            {selectedTools.includes(tool.id) && (
                              <span className="text-blue-400">✓</span>
                            )}
                          </div>
                          <p className="text-xs text-slate-400 mt-1">{tool.description}</p>
                          <span
                            className={`text-xs mt-2 inline-block px-2 py-0.5 rounded-full ${
                              tool.status === "active"
                                ? "bg-green-500/20 text-green-400"
                                : tool.status === "beta"
                                ? "bg-amber-500/20 text-amber-400"
                                : "bg-slate-600/50 text-slate-400"
                            }`}
                          >
                            {tool.status}
                          </span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-slate-500">
                  <span className="text-4xl block mb-2">🔧</span>
                  <p>Aucun outil disponible</p>
                </div>
              )}
            </div>
          )}

          {/* Step: Prompts */}
          {step === "prompts" && (
            <div className="space-y-4">
              <p className="text-slate-400 text-sm mb-4">
                Associez des modèles de prompts prédéfinis pour guider les réponses de cet employé.
              </p>
              
              {prompts.length > 0 ? (
                <div className="space-y-3">
                  {prompts.map((prompt) => (
                    <button
                      key={prompt.id}
                      onClick={() => togglePrompt(prompt.id)}
                      className={`w-full p-4 rounded-xl border-2 text-left transition-all ${
                        selectedPrompts.includes(prompt.id)
                          ? "border-green-500 bg-green-500/10"
                          : "border-slate-700 hover:border-slate-600"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-white">{prompt.name}</span>
                        <div className="flex items-center gap-2">
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full ${
                              prompt.scope === "enterprise"
                                ? "bg-purple-500/20 text-purple-300"
                                : "bg-amber-500/20 text-amber-300"
                            }`}
                          >
                            {prompt.scope === "enterprise" ? "🏢" : "🎯"}
                          </span>
                          {selectedPrompts.includes(prompt.id) && (
                            <span className="text-green-400">✓</span>
                          )}
                        </div>
                      </div>
                      <p className="text-xs text-slate-400">{prompt.description}</p>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-slate-500">
                  <span className="text-4xl block mb-2">📝</span>
                  <p>Aucun prompt disponible</p>
                </div>
              )}
            </div>
          )}

          {/* Step: Review */}
          {step === "review" && (
            <div className="space-y-6">
              <div className="bg-slate-800/50 rounded-xl p-6">
                <div className="flex items-start gap-4 mb-6">
                  <span className="text-5xl">{icon}</span>
                  <div>
                    <h3 className="text-xl font-bold text-white">{name}</h3>
                    <p className="text-slate-400">{description}</p>
                    <div className="flex gap-2 mt-2">
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        scope === "enterprise"
                          ? "bg-purple-500/20 text-purple-300"
                          : "bg-amber-500/20 text-amber-300"
                      }`}>
                        {scope === "enterprise" ? "🏢 Entreprise" : "🎯 Métier"}
                      </span>
                      <span className="text-xs px-2 py-1 rounded-full bg-slate-700 text-slate-300">
                        {CATEGORIES.find((c) => c.id === category)?.name || category}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium text-slate-400 mb-2">🔧 Outils ({selectedTools.length})</h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedTools.length > 0 ? (
                        selectedTools.map((toolId) => {
                          const tool = mcpTools.find((t) => t.id === toolId);
                          return tool ? (
                            <span key={toolId} className="text-xs bg-blue-500/20 text-blue-300 px-2 py-1 rounded-full">
                              {tool.icon} {tool.name}
                            </span>
                          ) : null;
                        })
                      ) : (
                        <span className="text-xs text-slate-500">Aucun outil sélectionné</span>
                      )}
                    </div>
                  </div>

                  <div>
                    <h4 className="text-sm font-medium text-slate-400 mb-2">📝 Prompts ({selectedPrompts.length})</h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedPrompts.length > 0 ? (
                        selectedPrompts.map((promptId) => {
                          const prompt = prompts.find((p) => p.id === promptId);
                          return prompt ? (
                            <span key={promptId} className="text-xs bg-green-500/20 text-green-300 px-2 py-1 rounded-full">
                              {prompt.name}
                            </span>
                          ) : null;
                        })
                      ) : (
                        <span className="text-xs text-slate-500">Aucun prompt sélectionné</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {error && (
                <div className="bg-red-500/10 border border-red-500/50 rounded-xl p-4 text-red-400 text-sm">
                  {error}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-700 flex justify-between">
          <button
            onClick={currentStepIndex === 0 ? onClose : handleBack}
            className="px-6 py-2 text-slate-400 hover:text-white transition-colors"
          >
            {currentStepIndex === 0 ? "Annuler" : "← Retour"}
          </button>

          {step === "review" ? (
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="px-8 py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white rounded-xl font-medium shadow-lg shadow-purple-500/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  Création...
                </>
              ) : (
                <>
                  ✨ Créer l&apos;employé
                </>
              )}
            </button>
          ) : (
            <button
              onClick={handleNext}
              disabled={!canProceed()}
              className="px-6 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Suivant →
            </button>
          )}
        </div>

        {/* AI Assistant */}
        <AIAssistant
          context="agent"
          currentData={{
            name,
            description,
            category,
          }}
          onSuggestion={(field, value) => {
            if (field === "name") setName(value);
            else if (field === "description") setDescription(value);
            else if (field === "system_prompt") setSystemPrompt(value);
          }}
        />
      </div>
    </div>
  );
}
