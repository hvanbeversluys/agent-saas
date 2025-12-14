"use client";

import { useEffect, useRef, useState, useCallback } from "react";

// Types d'événements SSE
export type SSEEventType =
  | "connected"
  | "workflow.started"
  | "workflow.step_completed"
  | "workflow.completed"
  | "workflow.failed"
  | "agent.response"
  | "agent.thinking"
  | "agent.tool_called"
  | "notification.info"
  | "notification.success"
  | "notification.error";

export interface SSEEvent {
  type: SSEEventType;
  tenant_id: string;
  user_id?: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface UseSSEOptions {
  /** Token d'authentification */
  token: string | null;
  /** Activer/désactiver la connexion */
  enabled?: boolean;
  /** Callback pour chaque événement */
  onEvent?: (event: SSEEvent) => void;
  /** Callback pour les erreurs */
  onError?: (error: Event) => void;
  /** Callback de connexion établie */
  onOpen?: () => void;
  /** URL de base de l'API */
  apiUrl?: string;
}

export interface UseSSEReturn {
  /** Connexion active */
  connected: boolean;
  /** Dernier événement reçu */
  lastEvent: SSEEvent | null;
  /** Historique des événements (limité) */
  events: SSEEvent[];
  /** Erreur de connexion */
  error: string | null;
  /** Reconnecter manuellement */
  reconnect: () => void;
  /** Déconnecter */
  disconnect: () => void;
}

const MAX_EVENTS_HISTORY = 50;

/**
 * Hook React pour les Server-Sent Events (SSE).
 * 
 * @example
 * ```tsx
 * const { connected, lastEvent, events } = useSSE({
 *   token: authToken,
 *   onEvent: (event) => {
 *     if (event.type === 'workflow.completed') {
 *       toast.success('Workflow terminé !');
 *     }
 *   }
 * });
 * ```
 */
export function useSSE(options: UseSSEOptions): UseSSEReturn {
  const {
    token,
    enabled = true,
    onEvent,
    onError,
    onOpen,
    apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  } = options;

  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<SSEEvent | null>(null);
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    setConnected(false);
  }, []);

  const connect = useCallback(() => {
    if (!token || !enabled) {
      return;
    }

    // Fermer la connexion existante
    disconnect();

    // Note: EventSource ne supporte pas les headers custom
    // On utilise un query param pour le token (moins sécurisé mais nécessaire pour SSE natif)
    // Alternative: utiliser fetch() avec streaming
    const url = `${apiUrl}/api/events/stream?token=${encodeURIComponent(token)}`;

    try {
      const eventSource = new EventSource(url);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        setConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
        onOpen?.();
      };

      eventSource.onerror = (e) => {
        setConnected(false);
        setError("Connection error");
        onError?.(e);

        // Auto-reconnect avec backoff exponentiel
        if (reconnectAttempts.current < 5) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
          reconnectAttempts.current++;
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };

      // Écouter tous les types d'événements
      const eventTypes: SSEEventType[] = [
        "connected",
        "workflow.started",
        "workflow.step_completed",
        "workflow.completed",
        "workflow.failed",
        "agent.response",
        "agent.thinking",
        "agent.tool_called",
        "notification.info",
        "notification.success",
        "notification.error",
      ];

      eventTypes.forEach((eventType) => {
        eventSource.addEventListener(eventType, (e: MessageEvent) => {
          try {
            const event: SSEEvent = JSON.parse(e.data);
            
            setLastEvent(event);
            setEvents((prev) => [event, ...prev].slice(0, MAX_EVENTS_HISTORY));
            onEvent?.(event);
          } catch (err) {
            console.error("Failed to parse SSE event:", err);
          }
        });
      });

      // Message générique (fallback)
      eventSource.onmessage = (e: MessageEvent) => {
        try {
          const event: SSEEvent = JSON.parse(e.data);
          setLastEvent(event);
          setEvents((prev) => [event, ...prev].slice(0, MAX_EVENTS_HISTORY));
          onEvent?.(event);
        } catch (err) {
          console.error("Failed to parse SSE message:", err);
        }
      };
    } catch (err) {
      setError("Failed to create EventSource");
      console.error("SSE connection error:", err);
    }
  }, [token, enabled, apiUrl, disconnect, onEvent, onError, onOpen]);

  const reconnect = useCallback(() => {
    reconnectAttempts.current = 0;
    connect();
  }, [connect]);

  // Connect on mount / token change
  useEffect(() => {
    if (token && enabled) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [token, enabled, connect, disconnect]);

  return {
    connected,
    lastEvent,
    events,
    error,
    reconnect,
    disconnect,
  };
}

/**
 * Hook simplifié pour les notifications.
 */
export function useNotifications(token: string | null) {
  const [notifications, setNotifications] = useState<SSEEvent[]>([]);

  const { connected, lastEvent } = useSSE({
    token,
    enabled: !!token,
    onEvent: (event) => {
      // Filtrer uniquement les notifications
      if (event.type.startsWith("notification.")) {
        setNotifications((prev) => [event, ...prev].slice(0, 20));
      }
    },
  });

  const clearNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  const removeNotification = useCallback((timestamp: string) => {
    setNotifications((prev) => prev.filter((n) => n.timestamp !== timestamp));
  }, []);

  return {
    connected,
    notifications,
    lastNotification: lastEvent?.type.startsWith("notification.") ? lastEvent : null,
    clearNotifications,
    removeNotification,
  };
}

/**
 * Hook pour suivre un workflow en temps réel.
 */
export function useWorkflowEvents(
  token: string | null,
  workflowId?: string
) {
  const [workflowStatus, setWorkflowStatus] = useState<string>("idle");
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [stepResults, setStepResults] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState<string | null>(null);

  const { connected, events } = useSSE({
    token,
    enabled: !!token && !!workflowId,
    onEvent: (event) => {
      if (!workflowId) return;
      
      const eventWorkflowId = (event.data as { workflow_id?: string }).workflow_id;
      if (eventWorkflowId !== workflowId) return;

      switch (event.type) {
        case "workflow.started":
          setWorkflowStatus("running");
          setCurrentStep(0);
          setStepResults([]);
          setError(null);
          break;
        case "workflow.step_completed":
          setCurrentStep((event.data as { step_index?: number }).step_index || 0);
          setStepResults((prev) => [...prev, event.data]);
          break;
        case "workflow.completed":
          setWorkflowStatus("completed");
          break;
        case "workflow.failed":
          setWorkflowStatus("failed");
          setError((event.data as { error?: string }).error || "Unknown error");
          break;
      }
    },
  });

  const reset = useCallback(() => {
    setWorkflowStatus("idle");
    setCurrentStep(0);
    setStepResults([]);
    setError(null);
  }, []);

  return {
    connected,
    workflowStatus,
    currentStep,
    stepResults,
    error,
    events: events.filter(
      (e) => (e.data as { workflow_id?: string }).workflow_id === workflowId
    ),
    reset,
  };
}
