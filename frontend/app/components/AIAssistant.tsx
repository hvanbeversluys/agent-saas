"use client";

import { useState } from "react";

interface AIAssistantProps {
  context: "prompt" | "workflow" | "agent";
  currentData?: {
    name?: string;
    description?: string;
    template?: string;
    category?: string;
  };
  onSuggestion: (field: string, value: string) => void;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  suggestions?: { field: string; label: string; value: string }[];
}

const CONTEXT_LABELS = {
  prompt: { icon: "📝", title: "Assistant Prompts", placeholder: "Décrivez ce que votre prompt doit faire..." },
  workflow: { icon: "⚡", title: "Assistant Workflows", placeholder: "Décrivez l'automatisation souhaitée..." },
  agent: { icon: "🤖", title: "Assistant Agents", placeholder: "Décrivez le rôle de votre agent..." },
};

const QUICK_ACTIONS = {
  prompt: [
    { icon: "💡", label: "Suggère un template", action: "suggest_template" },
    { icon: "✨", label: "Améliore le prompt", action: "improve_prompt" },
    { icon: "📋", label: "Ajoute des variables", action: "add_variables" },
    { icon: "🎯", label: "Rends-le plus précis", action: "make_precise" },
  ],
  workflow: [
    { icon: "📊", label: "Suggère des étapes", action: "suggest_steps" },
    { icon: "🔄", label: "Optimise le flux", action: "optimize_flow" },
    { icon: "⚠️", label: "Ajoute des conditions", action: "add_conditions" },
    { icon: "📅", label: "Propose un planning", action: "suggest_schedule" },
  ],
  agent: [
    { icon: "📝", label: "Rédige le prompt système", action: "write_system_prompt" },
    { icon: "🛠️", label: "Suggère des outils", action: "suggest_tools" },
    { icon: "🎭", label: "Définis la personnalité", action: "define_personality" },
    { icon: "📚", label: "Ajoute des exemples", action: "add_examples" },
  ],
};

export default function AIAssistant({
  context,
  currentData,
  onSuggestion,
}: AIAssistantProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const contextConfig = CONTEXT_LABELS[context];
  const quickActions = QUICK_ACTIONS[context];

  const sendMessage = async (customMessage?: string) => {
    const messageToSend = customMessage || input;
    if (!messageToSend.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: messageToSend,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch(`${apiUrl}/api/ai-assist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          context,
          message: messageToSend,
          current_data: currentData,
        }),
      });

      if (!response.ok) throw new Error("Erreur API");

      const data = await response.json();

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.response,
        suggestions: data.suggestions || [],
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "❌ Désolé, je n'ai pas pu traiter votre demande. Réessayez plus tard.",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickAction = (action: string) => {
    const actionMessages: Record<string, string> = {
      suggest_template: `Suggère-moi un template de prompt pour: ${currentData?.name || currentData?.description || "mon besoin"}`,
      improve_prompt: `Améliore ce prompt: "${currentData?.template?.substring(0, 200) || "Mon prompt actuel"}"`,
      add_variables: `Quelles variables devrais-je ajouter à mon prompt "${currentData?.name || "actuel"}"?`,
      make_precise: `Comment rendre mon prompt plus précis et efficace?`,
      suggest_steps: `Quelles étapes suggères-tu pour le workflow "${currentData?.name || "mon automatisation"}"?`,
      optimize_flow: `Comment optimiser ce workflow: ${currentData?.description || "mon workflow actuel"}`,
      add_conditions: `Quelles conditions devrais-je ajouter pour gérer les cas particuliers?`,
      suggest_schedule: `Quel planning recommandes-tu pour cette automatisation?`,
      write_system_prompt: `Écris-moi un prompt système pour un agent qui fait: ${currentData?.description || "mon besoin"}`,
      suggest_tools: `Quels outils MCP recommandes-tu pour cet agent?`,
      define_personality: `Définis la personnalité et le ton de cet agent`,
      add_examples: `Donne-moi des exemples de conversations pour entraîner cet agent`,
    };

    sendMessage(actionMessages[action] || action);
  };

  const applySuggestion = (field: string, value: string) => {
    onSuggestion(field, value);
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-gradient-to-br from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 rounded-full shadow-lg shadow-purple-500/30 flex items-center justify-center text-2xl transition-all hover:scale-110 z-40"
        title="Ouvrir l'assistant IA"
      >
        🤖
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 w-96 h-[500px] bg-slate-800 border border-slate-700 rounded-2xl shadow-2xl shadow-black/50 flex flex-col z-40 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-700 bg-gradient-to-r from-purple-600/20 to-blue-600/20">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{contextConfig.icon}</span>
          <div>
            <h3 className="font-semibold text-white">{contextConfig.title}</h3>
            <p className="text-xs text-slate-400">Je vous aide à créer</p>
          </div>
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className="text-slate-400 hover:text-white text-xl"
        >
          ×
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center py-6">
            <span className="text-4xl block mb-3">✨</span>
            <p className="text-slate-400 text-sm mb-4">
              Je suis là pour vous aider à créer.
            </p>
            {/* Quick Actions */}
            <div className="grid grid-cols-2 gap-2">
              {quickActions.map((action) => (
                <button
                  key={action.action}
                  onClick={() => handleQuickAction(action.action)}
                  className="flex items-center gap-2 p-2 bg-slate-700/50 hover:bg-slate-700 rounded-lg text-sm text-left transition-all"
                >
                  <span>{action.icon}</span>
                  <span className="text-slate-300">{action.label}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2 ${
                  message.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-slate-700 text-slate-200"
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                
                {/* Suggestions cliquables */}
                {message.suggestions && message.suggestions.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-600 space-y-2">
                    <p className="text-xs text-slate-400 mb-2">💡 Suggestions :</p>
                    {message.suggestions.map((suggestion, idx) => (
                      <button
                        key={idx}
                        onClick={() => applySuggestion(suggestion.field, suggestion.value)}
                        className="w-full text-left p-2 bg-slate-600/50 hover:bg-emerald-600/30 rounded-lg text-xs transition-all group"
                      >
                        <span className="text-slate-400 group-hover:text-emerald-400">
                          {suggestion.label}:
                        </span>
                        <p className="text-slate-200 mt-1 line-clamp-2">{suggestion.value}</p>
                        <span className="text-emerald-400 text-[10px] opacity-0 group-hover:opacity-100">
                          Cliquez pour appliquer →
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-700 rounded-2xl px-4 py-2 flex items-center gap-2">
              <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }}></div>
              <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
            </div>
          </div>
        )}
      </div>

      {/* Quick Actions (toujours visible) */}
      {messages.length > 0 && (
        <div className="px-4 py-2 border-t border-slate-700/50 flex gap-2 overflow-x-auto">
          {quickActions.slice(0, 3).map((action) => (
            <button
              key={action.action}
              onClick={() => handleQuickAction(action.action)}
              className="flex-shrink-0 flex items-center gap-1 px-2 py-1 bg-slate-700/50 hover:bg-slate-700 rounded-full text-xs text-slate-400 hover:text-white transition-all"
            >
              <span>{action.icon}</span>
              <span>{action.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="p-4 border-t border-slate-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
            placeholder={contextConfig.placeholder}
            className="flex-1 bg-slate-900/50 border border-slate-700 rounded-xl px-4 py-2 text-white text-sm focus:outline-none focus:border-purple-500"
            disabled={loading}
          />
          <button
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl transition-all"
          >
            →
          </button>
        </div>
      </div>
    </div>
  );
}
