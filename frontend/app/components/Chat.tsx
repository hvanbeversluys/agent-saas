"use client";

import { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface HandoffInfo {
  triggered: boolean;
  from_agent?: string;
  to_agent_id?: string;
  to_agent_name?: string;
  to_agent_icon?: string;
  reason?: string;
}

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  system_prompt?: string;
  mcp_tools: { id: string; name: string; icon: string }[];
  prompts: { id: string; name: string }[];
  is_active: boolean;
}

interface ChatProps {
  selectedAgent?: Agent | null;
  initialMessage?: string;
  onAgentHandoff?: (agentId: string) => void;
}

export default function Chat({ selectedAgent, initialMessage, onAgentHandoff }: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [lastHandoff, setLastHandoff] = useState<HandoffInfo | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Reset conversation when agent changes
  useEffect(() => {
    setMessages([]);
    setConversationId(null);
    if (selectedAgent) {
      // Auto-greeting when agent is selected
      setMessages([
        {
          role: "assistant",
          content: `${selectedAgent.icon} **${selectedAgent.name}** activé !\n\n${selectedAgent.description}\n\n_Comment puis-je vous aider ?_`,
        },
      ]);
    }
  }, [selectedAgent?.id]);

  // Handle initial message from prompt
  useEffect(() => {
    if (initialMessage) {
      setInput(initialMessage);
      inputRef.current?.focus();
    }
  }, [initialMessage]);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          conversation_id: conversationId,
          agent_id: selectedAgent?.id || null,
        }),
      });

      if (!response.ok) throw new Error("Erreur de communication");

      const data = await response.json();
      setConversationId(data.conversation_id);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.message.content },
      ]);
      
      // Gérer le handoff
      if (data.handoff?.triggered) {
        setLastHandoff(data.handoff);
        // Notifier le parent pour changer d'agent
        if (onAgentHandoff && data.handoff.to_agent_id) {
          onAgentHandoff(data.handoff.to_agent_id);
        }
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "❌ Erreur de connexion au backend. Vérifiez que le serveur est en ligne.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setConversationId(null);
    setLastHandoff(null);
    if (selectedAgent) {
      setMessages([
        {
          role: "assistant",
          content: `${selectedAgent.icon} **${selectedAgent.name}** - Nouvelle conversation\n\n_Comment puis-je vous aider ?_`,
        },
      ]);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-800/50 backdrop-blur-sm rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between bg-slate-800/80">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{selectedAgent?.icon || "💬"}</span>
          <div>
            <h2 className="font-semibold text-white text-sm">
              {selectedAgent?.name || "Chat Général"}
            </h2>
            <p className="text-xs text-slate-400">
              {selectedAgent ? `${selectedAgent.mcp_tools.length} outils connectés` : "Sélectionnez un agent"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {conversationId && (
            <span className="text-xs text-slate-500 font-mono hidden sm:block">
              #{conversationId.slice(0, 6)}
            </span>
          )}
          <button
            onClick={clearChat}
            className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded hover:bg-slate-700 transition-colors"
          >
            🗑️ Clear
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Handoff notification */}
        {lastHandoff?.triggered && (
          <div className="bg-gradient-to-r from-blue-600/20 to-purple-600/20 border border-blue-500/30 rounded-xl p-3 mb-4">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-xl">🔄</span>
              <span className="text-blue-300">
                Transfert vers <strong>{lastHandoff.to_agent_icon} {lastHandoff.to_agent_name}</strong>
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">{lastHandoff.reason}</p>
          </div>
        )}
        
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500">
            <span className="text-5xl mb-4">🤖</span>
            <p className="text-center text-lg font-medium text-slate-300">
              Bienvenue !
            </p>
            <p className="text-center text-sm mt-2 max-w-xs">
              Sélectionnez un agent dans le panneau de gauche, ou tapez <span className="text-blue-400">&quot;aide&quot;</span> pour commencer.
            </p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] px-4 py-3 rounded-2xl ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-br-md"
                    : "bg-slate-700/80 text-slate-100 rounded-bl-md"
                }`}
              >
                <div 
                  className="whitespace-pre-wrap text-sm prose prose-invert prose-sm max-w-none"
                  dangerouslySetInnerHTML={{ 
                    __html: msg.content
                      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                      .replace(/\*(.*?)\*/g, '<em>$1</em>')
                      .replace(/_(.*?)_/g, '<em>$1</em>')
                      .replace(/\n/g, '<br/>')
                  }}
                />
              </div>
            </div>
          ))
        )}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-slate-700 px-4 py-3 rounded-2xl rounded-bl-md">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></span>
                <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce [animation-delay:0.1s]"></span>
                <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce [animation-delay:0.2s]"></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={sendMessage} className="p-3 border-t border-slate-700 bg-slate-800/50">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={selectedAgent ? `Message à ${selectedAgent.name}...` : "Écrivez votre message..."}
            className="flex-1 bg-slate-700/50 border border-slate-600 rounded-xl px-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white px-5 py-3 rounded-xl font-medium transition-colors"
          >
            {isLoading ? "..." : "➤"}
          </button>
        </div>
      </form>
    </div>
  );
}
