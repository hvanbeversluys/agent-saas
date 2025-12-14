"use client";

import { useState, useEffect } from "react";

// ===== TYPES =====

interface WorkflowExecution {
  id: string;
  workflow_id: string;
  workflow_name: string;
  workflow_icon: string;
  status: "completed" | "failed" | "running" | "pending";
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  error_message?: string;
  steps: ExecutionStep[];
}

interface ExecutionStep {
  id: string;
  name: string;
  status: "completed" | "failed" | "running" | "pending" | "skipped";
  started_at?: string;
  completed_at?: string;
  output?: string;
  error?: string;
}

interface WorkflowStats {
  total_executions: number;
  successful: number;
  failed: number;
  pending: number;
  by_day: { date: string; count: number }[];
  by_workflow: { id: string; name: string; count: number; icon: string }[];
  actions_completed: number;
  time_saved_hours: number;
  executions: WorkflowExecution[];
}

interface Workflow {
  id: string;
  name: string;
  is_active: boolean;
}

interface UserDashboardProps {
  workflows: Workflow[];
}

// ===== TIME FILTERS =====

const TIME_FILTERS = [
  { id: "today", label: "Aujourd'hui", icon: "📅" },
  { id: "week", label: "Cette semaine", icon: "📆" },
  { id: "month", label: "Ce mois", icon: "🗓️" },
  { id: "quarter", label: "3 derniers mois", icon: "📊" },
  { id: "all", label: "Tout", icon: "♾️" },
];

// ===== MINI COMPONENTS =====

function MiniBarChart({ data, maxHeight = 60 }: { data: { label: string; value: number }[]; maxHeight?: number }) {
  const maxValue = Math.max(...data.map(d => d.value), 1);
  
  return (
    <div className="flex items-end gap-1" style={{ height: `${maxHeight + 20}px` }}>
      {data.map((item, idx) => (
        <div key={idx} className="flex-1 flex flex-col items-center gap-1">
          <div 
            className="w-full bg-gradient-to-t from-blue-600 to-blue-400 rounded-t-sm transition-all hover:from-blue-500 hover:to-blue-300 cursor-pointer"
            style={{ height: `${(item.value / maxValue) * maxHeight}px`, minHeight: item.value > 0 ? '4px' : '0' }}
            title={`${item.value} exécutions`}
          />
          <span className="text-[10px] text-slate-500">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

function DonutChart({ data, size = 90 }: { data: { label: string; value: number; color: string }[]; size?: number }) {
  const total = data.reduce((acc, d) => acc + d.value, 0);
  if (total === 0) {
    return (
      <div className="flex items-center justify-center" style={{ width: size, height: size }}>
        <div className="w-full h-full rounded-full border-4 border-slate-700 flex items-center justify-center">
          <span className="text-slate-500 text-xs">Aucune</span>
        </div>
      </div>
    );
  }
  
  let cumulativePercent = 0;
  const getCoordinatesForPercent = (percent: number) => {
    const x = Math.cos(2 * Math.PI * percent);
    const y = Math.sin(2 * Math.PI * percent);
    return [x, y];
  };

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg viewBox="-1 -1 2 2" style={{ transform: 'rotate(-90deg)' }}>
        {data.map((slice, idx) => {
          const [startX, startY] = getCoordinatesForPercent(cumulativePercent);
          const slicePercent = slice.value / total;
          cumulativePercent += slicePercent;
          const [endX, endY] = getCoordinatesForPercent(cumulativePercent);
          const largeArcFlag = slicePercent > 0.5 ? 1 : 0;
          const pathData = [
            `M ${startX} ${startY}`,
            `A 1 1 0 ${largeArcFlag} 1 ${endX} ${endY}`,
            `L 0 0`,
          ].join(' ');
          return <path key={idx} d={pathData} fill={slice.color} className="transition-opacity hover:opacity-80 cursor-pointer" />;
        })}
        <circle cx="0" cy="0" r="0.6" fill="#1e293b" />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center flex-col">
        <span className="text-lg font-bold text-white">{total}</span>
        <span className="text-[9px] text-slate-400">total</span>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    completed: { bg: "bg-emerald-500/20", text: "text-emerald-400", label: "✓ Terminé" },
    failed: { bg: "bg-red-500/20", text: "text-red-400", label: "✗ Erreur" },
    running: { bg: "bg-blue-500/20", text: "text-blue-400", label: "● En cours" },
    pending: { bg: "bg-amber-500/20", text: "text-amber-400", label: "◌ En attente" },
    skipped: { bg: "bg-slate-500/20", text: "text-slate-400", label: "○ Ignoré" },
  };
  const { bg, text, label } = config[status] || config.pending;
  return <span className={`text-xs px-2 py-1 rounded-full ${bg} ${text}`}>{label}</span>;
}

// ===== EXECUTION DETAIL MODAL =====

function ExecutionDetailModal({ 
  execution, 
  onClose,
  onAutoFix 
}: { 
  execution: WorkflowExecution; 
  onClose: () => void;
  onAutoFix: (executionId: string) => void;
}) {
  const duration = execution.duration_seconds 
    ? `${Math.floor(execution.duration_seconds / 60)}m ${execution.duration_seconds % 60}s`
    : "En cours...";

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <span className="text-2xl">{execution.workflow_icon || "⚡"}</span>
            <div>
              <h2 className="text-lg font-bold text-white">{execution.workflow_name}</h2>
              <p className="text-xs text-slate-400">
                Lancé le {new Date(execution.started_at).toLocaleString("fr-FR")}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-2xl">×</button>
        </div>

        {/* Summary */}
        <div className="p-5 border-b border-slate-700 bg-slate-800/50">
          <div className="flex items-center gap-6">
            <div>
              <span className="text-xs text-slate-500">Statut</span>
              <div className="mt-1"><StatusBadge status={execution.status} /></div>
            </div>
            <div>
              <span className="text-xs text-slate-500">Durée</span>
              <p className="text-white font-medium">{duration}</p>
            </div>
            <div>
              <span className="text-xs text-slate-500">Étapes</span>
              <p className="text-white font-medium">
                {execution.steps.filter(s => s.status === "completed").length}/{execution.steps.length}
              </p>
            </div>
            {execution.status === "failed" && (
              <button
                onClick={() => onAutoFix(execution.id)}
                className="ml-auto px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm font-medium flex items-center gap-2"
              >
                🔧 Auto-corriger
              </button>
            )}
          </div>
        </div>

        {/* Error Message */}
        {execution.error_message && (
          <div className="mx-5 mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
            <p className="text-xs text-red-400 font-medium mb-1">❌ Erreur rencontrée</p>
            <p className="text-sm text-red-300">{execution.error_message}</p>
          </div>
        )}

        {/* Steps Timeline */}
        <div className="flex-1 overflow-y-auto p-5">
          <h3 className="text-sm font-semibold text-slate-400 mb-4">📋 Étapes du workflow</h3>
          <div className="space-y-3">
            {execution.steps.map((step, idx) => (
              <div 
                key={step.id} 
                className={`p-4 rounded-xl border transition-all ${
                  step.status === "failed" 
                    ? "bg-red-500/10 border-red-500/30" 
                    : step.status === "completed"
                    ? "bg-slate-700/30 border-slate-600/50"
                    : step.status === "running"
                    ? "bg-blue-500/10 border-blue-500/30"
                    : "bg-slate-800/50 border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 rounded-full bg-slate-700 flex items-center justify-center text-xs text-slate-300">
                      {idx + 1}
                    </span>
                    <span className="font-medium text-white">{step.name}</span>
                  </div>
                  <StatusBadge status={step.status} />
                </div>
                {step.output && (
                  <div className="mt-3 p-2 bg-slate-900/50 rounded-lg">
                    <p className="text-xs text-slate-400 font-mono">{step.output}</p>
                  </div>
                )}
                {step.error && (
                  <div className="mt-3 p-2 bg-red-900/30 rounded-lg">
                    <p className="text-xs text-red-400 font-mono">{step.error}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-700 flex justify-between">
          <button 
            onClick={onClose}
            className="px-4 py-2 text-slate-400 hover:text-white"
          >
            Fermer
          </button>
          <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm">
            🔄 Relancer ce workflow
          </button>
        </div>
      </div>
    </div>
  );
}

// ===== ERRORS PAGE MODAL =====

function ErrorsPageModal({ 
  executions, 
  onClose,
  onAutoFix,
  onViewDetail
}: { 
  executions: WorkflowExecution[];
  onClose: () => void;
  onAutoFix: (executionId: string) => void;
  onViewDetail: (execution: WorkflowExecution) => void;
}) {
  const [fixing, setFixing] = useState<string | null>(null);
  const [fixResults, setFixResults] = useState<Record<string, { success: boolean; message: string }>>({});
  
  const failedExecutions = executions.filter(e => e.status === "failed");

  const handleAutoFixAll = async () => {
    for (const exec of failedExecutions) {
      setFixing(exec.id);
      await new Promise(resolve => setTimeout(resolve, 1500)); // Simulate fix
      setFixResults(prev => ({
        ...prev,
        [exec.id]: { 
          success: Math.random() > 0.3, 
          message: Math.random() > 0.3 
            ? "Configuration corrigée. Prêt à relancer." 
            : "Nécessite une intervention manuelle."
        }
      }));
    }
    setFixing(null);
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-700 bg-red-500/5">
          <div className="flex items-center gap-3">
            <span className="text-3xl">⚠️</span>
            <div>
              <h2 className="text-xl font-bold text-white">Erreurs détectées</h2>
              <p className="text-sm text-slate-400">
                {failedExecutions.length} workflow{failedExecutions.length > 1 ? "s" : ""} en erreur
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-2xl">×</button>
        </div>

        {/* AI Fix Banner */}
        <div className="mx-5 mt-4 p-4 bg-gradient-to-r from-purple-600/20 to-blue-600/20 border border-purple-500/30 rounded-xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-2xl">🤖</span>
              <div>
                <h3 className="font-semibold text-white">Agent Auto-Correctif</h3>
                <p className="text-xs text-slate-400">
                  Laissez l'IA analyser et corriger automatiquement les erreurs
                </p>
              </div>
            </div>
            <button
              onClick={handleAutoFixAll}
              disabled={fixing !== null}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium flex items-center gap-2"
            >
              {fixing ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Correction en cours...
                </>
              ) : (
                <>🔧 Tout corriger</>
              )}
            </button>
          </div>
        </div>

        {/* Error List */}
        <div className="flex-1 overflow-y-auto p-5 space-y-3">
          {failedExecutions.length === 0 ? (
            <div className="text-center py-12">
              <span className="text-5xl block mb-4">✅</span>
              <p className="text-slate-400">Aucune erreur à corriger !</p>
            </div>
          ) : (
            failedExecutions.map((exec) => (
              <div 
                key={exec.id}
                className={`p-4 rounded-xl border transition-all ${
                  fixing === exec.id 
                    ? "bg-purple-500/10 border-purple-500/30 animate-pulse"
                    : fixResults[exec.id]
                    ? fixResults[exec.id].success
                      ? "bg-emerald-500/10 border-emerald-500/30"
                      : "bg-amber-500/10 border-amber-500/30"
                    : "bg-red-500/10 border-red-500/30"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <span className="text-xl">{exec.workflow_icon || "⚡"}</span>
                    <div>
                      <h4 className="font-medium text-white">{exec.workflow_name}</h4>
                      <p className="text-xs text-slate-400">
                        {new Date(exec.started_at).toLocaleString("fr-FR")}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {fixResults[exec.id] ? (
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        fixResults[exec.id].success 
                          ? "bg-emerald-500/20 text-emerald-400"
                          : "bg-amber-500/20 text-amber-400"
                      }`}>
                        {fixResults[exec.id].success ? "✓ Corrigé" : "⚠ À vérifier"}
                      </span>
                    ) : (
                      <StatusBadge status="failed" />
                    )}
                  </div>
                </div>

                {/* Error Details */}
                <div className="p-3 bg-slate-900/50 rounded-lg mb-3">
                  <p className="text-xs text-red-400 font-medium mb-1">Erreur :</p>
                  <p className="text-sm text-slate-300">{exec.error_message || "Erreur inconnue"}</p>
                </div>

                {/* Fix Result */}
                {fixResults[exec.id] && (
                  <div className={`p-3 rounded-lg mb-3 ${
                    fixResults[exec.id].success ? "bg-emerald-900/30" : "bg-amber-900/30"
                  }`}>
                    <p className={`text-xs font-medium mb-1 ${
                      fixResults[exec.id].success ? "text-emerald-400" : "text-amber-400"
                    }`}>
                      {fixResults[exec.id].success ? "🔧 Diagnostic IA :" : "⚠️ Attention :"}
                    </p>
                    <p className="text-sm text-slate-300">{fixResults[exec.id].message}</p>
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onViewDetail(exec)}
                    className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-xs"
                  >
                    👁️ Voir détail
                  </button>
                  <button
                    onClick={() => onAutoFix(exec.id)}
                    disabled={fixing !== null}
                    className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg text-xs"
                  >
                    🔧 Corriger
                  </button>
                  {fixResults[exec.id]?.success && (
                    <button className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs">
                      🔄 Relancer
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-700">
          <button 
            onClick={onClose}
            className="w-full px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg"
          >
            Fermer
          </button>
        </div>
      </div>
    </div>
  );
}

// ===== MAIN COMPONENT =====

export default function UserDashboard({ workflows }: UserDashboardProps) {
  const [stats, setStats] = useState<WorkflowStats | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [timeFilter, setTimeFilter] = useState("week");
  const [workflowFilter, setWorkflowFilter] = useState<string>("all");
  
  // Modals
  const [selectedExecution, setSelectedExecution] = useState<WorkflowExecution | null>(null);
  const [showErrorsPage, setShowErrorsPage] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    fetchStats();
  }, [timeFilter, workflowFilter]);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ period: timeFilter });
      if (workflowFilter !== "all") params.append("workflow_id", workflowFilter);
      
      const res = await fetch(`${apiUrl}/api/stats/workflows?${params}`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      } else {
        setStats(generateDemoStats());
      }
    } catch {
      setStats(generateDemoStats());
    } finally {
      setLoading(false);
    }
  };

  const generateDemoStats = (): WorkflowStats => {
    const days = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];
    
    const demoExecutions: WorkflowExecution[] = [
      {
        id: "exec-1",
        workflow_id: "wf-1",
        workflow_name: "Relance clients",
        workflow_icon: "📧",
        status: "completed",
        started_at: new Date(Date.now() - 3600000).toISOString(),
        completed_at: new Date(Date.now() - 3500000).toISOString(),
        duration_seconds: 100,
        steps: [
          { id: "s1", name: "Récupérer liste clients", status: "completed", output: "12 clients trouvés" },
          { id: "s2", name: "Générer emails personnalisés", status: "completed", output: "12 emails générés" },
          { id: "s3", name: "Envoyer via Gmail", status: "completed", output: "12 emails envoyés" },
        ]
      },
      {
        id: "exec-2",
        workflow_id: "wf-2",
        workflow_name: "Prospection B2B",
        workflow_icon: "🎯",
        status: "failed",
        started_at: new Date(Date.now() - 7200000).toISOString(),
        duration_seconds: 45,
        error_message: "Impossible de se connecter au CRM. Vérifiez vos identifiants API.",
        steps: [
          { id: "s1", name: "Rechercher prospects", status: "completed", output: "25 prospects trouvés" },
          { id: "s2", name: "Enrichir données", status: "completed", output: "Données enrichies" },
          { id: "s3", name: "Ajouter au CRM", status: "failed", error: "API Error 401: Unauthorized" },
          { id: "s4", name: "Envoyer email intro", status: "skipped" },
        ]
      },
      {
        id: "exec-3",
        workflow_id: "wf-3",
        workflow_name: "Rapport SEO hebdo",
        workflow_icon: "📊",
        status: "completed",
        started_at: new Date(Date.now() - 86400000).toISOString(),
        completed_at: new Date(Date.now() - 86000000).toISOString(),
        duration_seconds: 400,
        steps: [
          { id: "s1", name: "Collecter métriques GSC", status: "completed", output: "1250 mots-clés analysés" },
          { id: "s2", name: "Analyser positions", status: "completed", output: "+15 positions en moyenne" },
          { id: "s3", name: "Générer rapport PDF", status: "completed", output: "Rapport généré: rapport_seo_semaine_49.pdf" },
          { id: "s4", name: "Envoyer par email", status: "completed", output: "Envoyé à 3 destinataires" },
        ]
      },
      {
        id: "exec-4",
        workflow_id: "wf-4",
        workflow_name: "Facturation auto",
        workflow_icon: "🧾",
        status: "failed",
        started_at: new Date(Date.now() - 172800000).toISOString(),
        duration_seconds: 30,
        error_message: "Le template de facture est introuvable. Fichier supprimé ou déplacé.",
        steps: [
          { id: "s1", name: "Récupérer prestations", status: "completed", output: "8 prestations à facturer" },
          { id: "s2", name: "Charger template", status: "failed", error: "FileNotFoundError: template_facture.docx" },
          { id: "s3", name: "Générer factures", status: "skipped" },
        ]
      },
      {
        id: "exec-5",
        workflow_id: "wf-1",
        workflow_name: "Relance clients",
        workflow_icon: "📧",
        status: "running",
        started_at: new Date(Date.now() - 120000).toISOString(),
        steps: [
          { id: "s1", name: "Récupérer liste clients", status: "completed", output: "8 clients trouvés" },
          { id: "s2", name: "Générer emails personnalisés", status: "running" },
          { id: "s3", name: "Envoyer via Gmail", status: "pending" },
        ]
      },
    ];

    return {
      total_executions: 47,
      successful: 42,
      failed: 3,
      pending: 2,
      by_day: days.map((day) => ({
        date: day,
        count: Math.floor(Math.random() * 12) + 2
      })),
      by_workflow: [
        { id: "wf-1", name: "Relance clients", count: 18, icon: "📧" },
        { id: "wf-2", name: "Prospection B2B", count: 12, icon: "🎯" },
        { id: "wf-3", name: "Rapport SEO", count: 9, icon: "📊" },
        { id: "wf-4", name: "Facturation", count: 8, icon: "🧾" },
      ],
      actions_completed: 156,
      time_saved_hours: 24,
      executions: demoExecutions,
    };
  };

  const handleAutoFix = async (executionId: string) => {
    // TODO: Call backend AI fix endpoint
    console.log("Auto-fixing:", executionId);
  };

  if (loading && !stats) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-slate-800/50 border border-slate-700 rounded-2xl h-32" />
        ))}
      </div>
    );
  }

  if (!stats) return null;

  const successRate = stats.total_executions > 0 
    ? Math.round((stats.successful / stats.total_executions) * 100) 
    : 100;

  const failedExecutions = stats.executions?.filter(e => e.status === "failed") || [];

  return (
    <div className="space-y-6">
      {/* Filters Bar */}
      <div className="flex flex-wrap items-center gap-4 p-4 bg-slate-800/30 border border-slate-700 rounded-xl">
        {/* Time Filter */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Période :</span>
          <div className="flex gap-1 bg-slate-800 rounded-lg p-1">
            {TIME_FILTERS.map((filter) => (
              <button
                key={filter.id}
                onClick={() => setTimeFilter(filter.id)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  timeFilter === filter.id
                    ? "bg-blue-600 text-white"
                    : "text-slate-400 hover:text-white hover:bg-slate-700"
                }`}
              >
                {filter.icon} {filter.label}
              </button>
            ))}
          </div>
        </div>

        {/* Workflow Filter */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Workflow :</span>
          <select
            value={workflowFilter}
            onChange={(e) => setWorkflowFilter(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
          >
            <option value="all">Tous les workflows</option>
            {stats.by_workflow.map((wf) => (
              <option key={wf.id} value={wf.id}>
                {wf.icon} {wf.name}
              </option>
            ))}
          </select>
        </div>

        {/* Refresh */}
        <button
          onClick={fetchStats}
          disabled={loading}
          className="ml-auto px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-xs flex items-center gap-1"
        >
          {loading ? (
            <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            "🔄"
          )}
          Actualiser
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-slate-400 text-sm">Workflows lancés</span>
            <span className="text-2xl">🚀</span>
          </div>
          <p className="text-3xl font-bold text-white">{stats.total_executions}</p>
          <p className="text-xs text-emerald-400 mt-1">{TIME_FILTERS.find(f => f.id === timeFilter)?.label}</p>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-slate-400 text-sm">Actions réalisées</span>
            <span className="text-2xl">✅</span>
          </div>
          <p className="text-3xl font-bold text-white">{stats.actions_completed}</p>
          <p className="text-xs text-blue-400 mt-1">Emails, docs, analyses...</p>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-slate-400 text-sm">Taux de succès</span>
            <span className="text-2xl">📈</span>
          </div>
          <p className={`text-3xl font-bold ${successRate >= 90 ? 'text-emerald-400' : successRate >= 70 ? 'text-amber-400' : 'text-red-400'}`}>
            {successRate}%
          </p>
          <p className="text-xs text-slate-500 mt-1">{stats.successful} réussis / {stats.failed} échoués</p>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-slate-400 text-sm">Temps économisé</span>
            <span className="text-2xl">⏱️</span>
          </div>
          <p className="text-3xl font-bold text-purple-400">{stats.time_saved_hours}h</p>
          <p className="text-xs text-slate-500 mt-1">≈ {Math.round(stats.time_saved_hours / 8)} jours de travail</p>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Activity Chart */}
        <div className="lg:col-span-2 bg-slate-800/50 border border-slate-700 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-white">📊 Activité</h3>
            <span className="text-xs text-slate-500">Workflows exécutés par jour</span>
          </div>
          <MiniBarChart data={stats.by_day.map(d => ({ label: d.date, value: d.count }))} maxHeight={60} />
        </div>

        {/* Status Donut */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-white">📈 Statuts</h3>
            {failedExecutions.length > 0 && (
              <button
                onClick={() => setShowErrorsPage(true)}
                className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1"
              >
                ⚠️ {failedExecutions.length} erreur{failedExecutions.length > 1 ? "s" : ""}
              </button>
            )}
          </div>
          <div className="flex items-center justify-center gap-4">
            <DonutChart 
              data={[
                { label: "Réussis", value: stats.successful, color: "#10b981" },
                { label: "Échoués", value: stats.failed, color: "#ef4444" },
                { label: "En cours", value: stats.pending, color: "#f59e0b" },
              ]}
              size={80}
            />
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-emerald-500" />
                <span className="text-slate-300">Réussis ({stats.successful})</span>
              </div>
              <button
                onClick={() => setShowErrorsPage(true)}
                className="flex items-center gap-2 hover:bg-red-500/10 px-2 py-1 -mx-2 rounded transition-colors"
              >
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <span className="text-slate-300">Échoués ({stats.failed})</span>
              </button>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-amber-500" />
                <span className="text-slate-300">En cours ({stats.pending})</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Executions */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-white">🕐 Exécutions récentes</h3>
          <span className="text-xs text-slate-500">Cliquez pour voir le détail</span>
        </div>
        <div className="space-y-2">
          {stats.executions?.slice(0, 5).map((exec) => (
            <button
              key={exec.id}
              onClick={() => setSelectedExecution(exec)}
              className="w-full flex items-center gap-4 p-3 bg-slate-700/30 hover:bg-slate-700/50 rounded-xl transition-all text-left"
            >
              <span className="text-xl">{exec.workflow_icon || "⚡"}</span>
              <div className="flex-1 min-w-0">
                <h4 className="font-medium text-white truncate">{exec.workflow_name}</h4>
                <p className="text-xs text-slate-400">
                  {new Date(exec.started_at).toLocaleString("fr-FR")}
                  {exec.duration_seconds && ` • ${Math.floor(exec.duration_seconds / 60)}m ${exec.duration_seconds % 60}s`}
                </p>
              </div>
              <StatusBadge status={exec.status} />
              <span className="text-slate-500">→</span>
            </button>
          ))}
        </div>
      </div>

      {/* Top Workflows */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-5">
        <h3 className="font-semibold text-white mb-4">🏆 Workflows les plus utilisés</h3>
        <div className="space-y-3">
          {stats.by_workflow.map((wf, idx) => {
            const maxCount = Math.max(...stats.by_workflow.map(w => w.count));
            const percentage = (wf.count / maxCount) * 100;
            return (
              <div key={idx} className="flex items-center gap-3">
                <span className="text-xl w-8">{wf.icon}</span>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-white">{wf.name}</span>
                    <span className="text-xs text-slate-400">{wf.count} exécutions</span>
                  </div>
                  <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-blue-600 to-purple-600 rounded-full transition-all" style={{ width: `${percentage}%` }} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Modals */}
      {selectedExecution && (
        <ExecutionDetailModal
          execution={selectedExecution}
          onClose={() => setSelectedExecution(null)}
          onAutoFix={handleAutoFix}
        />
      )}

      {showErrorsPage && (
        <ErrorsPageModal
          executions={stats.executions || []}
          onClose={() => setShowErrorsPage(false)}
          onAutoFix={handleAutoFix}
          onViewDetail={(exec) => {
            setShowErrorsPage(false);
            setSelectedExecution(exec);
          }}
        />
      )}
    </div>
  );
}
