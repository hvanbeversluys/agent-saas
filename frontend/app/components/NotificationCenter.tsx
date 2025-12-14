"use client";

import { useEffect, useState } from "react";
import { useNotifications, SSEEvent } from "../hooks/useSSE";
import { useAuth } from "../contexts/AuthContext";

interface NotificationToast {
  id: string;
  type: "info" | "success" | "error" | "warning";
  title: string;
  message: string;
  timestamp: Date;
}

/**
 * Composant de notifications temps réel.
 * Affiche les toasts pour les événements SSE.
 */
export function NotificationCenter() {
  const { token } = useAuth();
  const { connected, notifications, removeNotification } = useNotifications(token);
  const [toasts, setToasts] = useState<NotificationToast[]>([]);

  // Convertir les SSE events en toasts
  useEffect(() => {
    if (notifications.length === 0) return;

    const latestNotification = notifications[0];
    const toastType = latestNotification.type.replace("notification.", "") as NotificationToast["type"];
    
    const newToast: NotificationToast = {
      id: latestNotification.timestamp,
      type: toastType,
      title: getToastTitle(latestNotification),
      message: (latestNotification.data as { message?: string }).message || "",
      timestamp: new Date(latestNotification.timestamp),
    };

    setToasts((prev) => [newToast, ...prev].slice(0, 5));

    // Auto-dismiss après 5 secondes
    const timeout = setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== newToast.id));
      removeNotification(latestNotification.timestamp);
    }, 5000);

    return () => clearTimeout(timeout);
  }, [notifications, removeNotification]);

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  if (toasts.length === 0) {
    return null;
  }

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {/* Connection indicator */}
      {!connected && (
        <div className="bg-yellow-900/90 border border-yellow-600 rounded-lg p-3 flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
          <span className="text-sm text-yellow-200">Reconnexion...</span>
        </div>
      )}
      
      {/* Toasts */}
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`
            rounded-lg p-4 shadow-lg border backdrop-blur-sm
            animate-in slide-in-from-right duration-300
            ${getToastStyles(toast.type)}
          `}
        >
          <div className="flex items-start gap-3">
            <div className="text-xl">{getToastIcon(toast.type)}</div>
            <div className="flex-1 min-w-0">
              <h4 className="font-medium text-sm">{toast.title}</h4>
              {toast.message && (
                <p className="text-sm opacity-90 mt-0.5 truncate">{toast.message}</p>
              )}
            </div>
            <button
              onClick={() => dismissToast(toast.id)}
              className="text-white/60 hover:text-white transition-colors"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function getToastTitle(event: SSEEvent): string {
  const data = event.data as { title?: string; workflow_id?: string };
  
  if (data.title) return data.title;
  
  switch (event.type) {
    case "workflow.started":
      return "Workflow démarré";
    case "workflow.completed":
      return "Workflow terminé ✓";
    case "workflow.failed":
      return "Workflow échoué";
    case "notification.success":
      return "Succès";
    case "notification.error":
      return "Erreur";
    case "notification.info":
    default:
      return "Information";
  }
}

function getToastStyles(type: NotificationToast["type"]): string {
  switch (type) {
    case "success":
      return "bg-emerald-900/90 border-emerald-600 text-emerald-100";
    case "error":
      return "bg-red-900/90 border-red-600 text-red-100";
    case "warning":
      return "bg-amber-900/90 border-amber-600 text-amber-100";
    case "info":
    default:
      return "bg-blue-900/90 border-blue-600 text-blue-100";
  }
}

function getToastIcon(type: NotificationToast["type"]): string {
  switch (type) {
    case "success":
      return "✅";
    case "error":
      return "❌";
    case "warning":
      return "⚠️";
    case "info":
    default:
      return "ℹ️";
  }
}

/**
 * Composant indicateur de connexion SSE.
 * Petit point qui indique l'état de la connexion temps réel.
 */
export function ConnectionIndicator() {
  const { token } = useAuth();
  const { connected } = useNotifications(token);

  return (
    <div className="flex items-center gap-2" title={connected ? "Connecté" : "Déconnecté"}>
      <div
        className={`w-2 h-2 rounded-full transition-colors ${
          connected ? "bg-emerald-500" : "bg-red-500 animate-pulse"
        }`}
      />
      <span className="text-xs text-gray-500">
        {connected ? "Live" : "..."}
      </span>
    </div>
  );
}

/**
 * Barre de progression pour un workflow en cours.
 */
export function WorkflowProgress({
  workflowId,
  totalSteps = 5,
}: {
  workflowId: string;
  totalSteps?: number;
}) {
  const { token } = useAuth();
  const [status, setStatus] = useState<"idle" | "running" | "completed" | "failed">("idle");
  const [currentStep, setCurrentStep] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Note: On utiliserait useWorkflowEvents ici
  // Pour l'exemple, on simule avec useNotifications
  const { connected } = useNotifications(token);

  const progress = totalSteps > 0 ? (currentStep / totalSteps) * 100 : 0;

  if (status === "idle") {
    return null;
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium">
          {status === "running" && "Exécution en cours..."}
          {status === "completed" && "✅ Terminé"}
          {status === "failed" && "❌ Échec"}
        </span>
        <span className="text-xs text-gray-400">
          {currentStep}/{totalSteps} étapes
        </span>
      </div>
      
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all duration-500 ${
            status === "failed" ? "bg-red-500" :
            status === "completed" ? "bg-emerald-500" : "bg-blue-500"
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>
      
      {error && (
        <p className="text-xs text-red-400 mt-2">{error}</p>
      )}
    </div>
  );
}
