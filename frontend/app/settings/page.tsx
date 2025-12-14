"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface UsageStats {
  current_period: string;
  workflow_executions: number;
  agent_calls: number;
  mcp_tool_calls: number;
  limits: {
    max_executions_per_month: number;
    max_users: number;
    max_agents: number;
    max_workflows: number;
  };
  usage_percentage: {
    executions: number;
  };
}

interface TeamMember {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string;
  role: string;
  is_active: boolean;
}

export default function SettingsPage() {
  const { user, tenant, isAuthenticated, isLoading: authLoading, logout, updateUser } = useAuth();
  const router = useRouter();
  
  const [activeTab, setActiveTab] = useState<'profile' | 'company' | 'team' | 'billing'>('profile');
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  
  // Profile form
  const [profileForm, setProfileForm] = useState({
    first_name: '',
    last_name: '',
    job_title: '',
  });
  
  // Team data
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [usageStats, setUsageStats] = useState<UsageStats | null>(null);
  
  // Invite form
  const [inviteForm, setInviteForm] = useState({
    email: '',
    role: 'member',
    first_name: '',
    last_name: '',
  });
  const [showInviteModal, setShowInviteModal] = useState(false);

  // Redirect if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  // Load initial data
  useEffect(() => {
    if (user) {
      setProfileForm({
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        job_title: user.job_title || '',
      });
    }
  }, [user]);

  // Load team members
  useEffect(() => {
    const loadTeam = async () => {
      if (!isAuthenticated) return;
      const token = localStorage.getItem('access_token');
      if (!token) return;

      try {
        const response = await fetch(`${API_URL}/api/users`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (response.ok) {
          const data = await response.json();
          setTeamMembers(data);
        }
      } catch (error) {
        console.error('Error loading team:', error);
      }
    };

    if (activeTab === 'team') {
      loadTeam();
    }
  }, [activeTab, isAuthenticated]);

  // Load usage stats
  useEffect(() => {
    const loadUsage = async () => {
      if (!isAuthenticated) return;
      const token = localStorage.getItem('access_token');
      if (!token) return;

      try {
        const response = await fetch(`${API_URL}/api/usage/stats`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (response.ok) {
          const data = await response.json();
          setUsageStats(data);
        }
      } catch (error) {
        console.error('Error loading usage:', error);
      }
    };

    if (activeTab === 'billing') {
      loadUsage();
    }
  }, [activeTab, isAuthenticated]);

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setMessage(null);

    try {
      await updateUser(profileForm);
      setMessage({ type: 'success', text: 'Profil mis à jour avec succès' });
    } catch (error) {
      setMessage({ type: 'error', text: error instanceof Error ? error.message : 'Erreur' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    const token = localStorage.getItem('access_token');

    try {
      const response = await fetch(`${API_URL}/api/users/invite`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(inviteForm),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Erreur lors de l\'invitation');
      }

      const newMember = await response.json();
      setTeamMembers(prev => [...prev, newMember]);
      setShowInviteModal(false);
      setInviteForm({ email: '', role: 'member', first_name: '', last_name: '' });
      setMessage({ type: 'success', text: 'Invitation envoyée avec succès' });
    } catch (error) {
      setMessage({ type: 'error', text: error instanceof Error ? error.message : 'Erreur' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteMember = async (memberId: string) => {
    if (!confirm('Êtes-vous sûr de vouloir supprimer cet utilisateur ?')) return;
    
    const token = localStorage.getItem('access_token');
    try {
      const response = await fetch(`${API_URL}/api/users/${memberId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Erreur');
      }

      setTeamMembers(prev => prev.filter(m => m.id !== memberId));
      setMessage({ type: 'success', text: 'Utilisateur supprimé' });
    } catch (error) {
      setMessage({ type: 'error', text: error instanceof Error ? error.message : 'Erreur' });
    }
  };

  if (authLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 flex items-center justify-center">
        <div className="animate-pulse text-gray-400">Chargement...</div>
      </div>
    );
  }

  const roleLabels: Record<string, string> = {
    owner: 'Propriétaire',
    admin: 'Administrateur',
    manager: 'Manager',
    member: 'Membre',
    viewer: 'Lecteur',
  };

  const planLabels: Record<string, { name: string; color: string }> = {
    free: { name: 'Gratuit', color: 'gray' },
    starter: { name: 'Starter', color: 'blue' },
    business: { name: 'Business', color: 'purple' },
    enterprise: { name: 'Enterprise', color: 'amber' },
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white">
      {/* Header */}
      <header className="border-b border-gray-700 bg-gray-800/50">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center space-x-2">
            <span className="text-2xl">🤖</span>
            <span className="font-bold">Agent SaaS</span>
          </Link>
          <div className="flex items-center space-x-4">
            <span className="text-gray-400">{user?.email}</span>
            <button
              onClick={() => logout()}
              className="text-gray-400 hover:text-white transition-colors"
            >
              Déconnexion
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-8">⚙️ Paramètres</h1>

        {/* Message */}
        {message && (
          <div className={`mb-6 p-4 rounded-lg ${
            message.type === 'success' 
              ? 'bg-emerald-500/10 border border-emerald-500/50 text-emerald-400'
              : 'bg-red-500/10 border border-red-500/50 text-red-400'
          }`}>
            {message.text}
          </div>
        )}

        <div className="flex gap-8">
          {/* Sidebar */}
          <div className="w-48 flex-shrink-0">
            <nav className="space-y-1">
              {[
                { id: 'profile', label: '👤 Mon profil' },
                { id: 'company', label: '🏢 Entreprise' },
                { id: 'team', label: '👥 Équipe' },
                { id: 'billing', label: '💳 Facturation' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as typeof activeTab)}
                  className={`w-full text-left px-4 py-2 rounded-lg transition-colors ${
                    activeTab === tab.id
                      ? 'bg-gray-700 text-white'
                      : 'text-gray-400 hover:text-white hover:bg-gray-700/50'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {/* Content */}
          <div className="flex-1 bg-gray-800/50 border border-gray-700 rounded-2xl p-6">
            {/* Profile Tab */}
            {activeTab === 'profile' && (
              <div>
                <h2 className="text-lg font-semibold mb-6">Mon profil</h2>
                <form onSubmit={handleProfileSubmit} className="space-y-4 max-w-md">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-gray-400 mb-2">Prénom</label>
                      <input
                        type="text"
                        value={profileForm.first_name}
                        onChange={(e) => setProfileForm(p => ({ ...p, first_name: e.target.value }))}
                        className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-2">Nom</label>
                      <input
                        type="text"
                        value={profileForm.last_name}
                        onChange={(e) => setProfileForm(p => ({ ...p, last_name: e.target.value }))}
                        className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Email</label>
                    <input
                      type="email"
                      value={user?.email || ''}
                      disabled
                      className="w-full px-4 py-2 bg-gray-700/30 border border-gray-600 rounded-lg text-gray-400"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Fonction</label>
                    <input
                      type="text"
                      value={profileForm.job_title}
                      onChange={(e) => setProfileForm(p => ({ ...p, job_title: e.target.value }))}
                      className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white"
                      placeholder="Ex: Directeur Commercial"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Rôle</label>
                    <span className={`inline-block px-3 py-1 rounded-full text-sm ${
                      user?.role === 'owner' ? 'bg-amber-500/20 text-amber-400' : 'bg-blue-500/20 text-blue-400'
                    }`}>
                      {roleLabels[user?.role || 'member']}
                    </span>
                  </div>
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="px-6 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {isLoading ? 'Enregistrement...' : 'Enregistrer'}
                  </button>
                </form>
              </div>
            )}

            {/* Company Tab */}
            {activeTab === 'company' && tenant && (
              <div>
                <h2 className="text-lg font-semibold mb-6">Informations entreprise</h2>
                <div className="space-y-4 max-w-md">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Nom</label>
                    <div className="px-4 py-2 bg-gray-700/30 border border-gray-600 rounded-lg">
                      {tenant.name}
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Identifiant</label>
                    <div className="px-4 py-2 bg-gray-700/30 border border-gray-600 rounded-lg text-gray-400">
                      {tenant.slug}
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Plan actuel</label>
                    <span className={`inline-block px-3 py-1 rounded-full text-sm bg-${planLabels[tenant.plan]?.color || 'gray'}-500/20 text-${planLabels[tenant.plan]?.color || 'gray'}-400`}>
                      {planLabels[tenant.plan]?.name || tenant.plan}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Team Tab */}
            {activeTab === 'team' && (
              <div>
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-lg font-semibold">
                    Équipe ({teamMembers.length}/{tenant?.max_users || 0})
                  </h2>
                  {user?.role === 'owner' || user?.role === 'admin' ? (
                    <button
                      onClick={() => setShowInviteModal(true)}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors text-sm"
                    >
                      + Inviter
                    </button>
                  ) : null}
                </div>

                <div className="space-y-3">
                  {teamMembers.map((member) => (
                    <div
                      key={member.id}
                      className="flex items-center justify-between p-4 bg-gray-700/30 border border-gray-600 rounded-lg"
                    >
                      <div className="flex items-center space-x-4">
                        <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center font-bold">
                          {member.full_name?.charAt(0) || member.email.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <div className="font-medium">{member.full_name || member.email}</div>
                          <div className="text-sm text-gray-400">{member.email}</div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-4">
                        <span className={`px-2 py-1 rounded text-xs ${
                          member.role === 'owner' ? 'bg-amber-500/20 text-amber-400' :
                          member.role === 'admin' ? 'bg-purple-500/20 text-purple-400' :
                          'bg-gray-500/20 text-gray-400'
                        }`}>
                          {roleLabels[member.role]}
                        </span>
                        {member.role !== 'owner' && member.id !== user?.id && (
                          <button
                            onClick={() => handleDeleteMember(member.id)}
                            className="text-red-400 hover:text-red-300 text-sm"
                          >
                            Supprimer
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Invite Modal */}
                {showInviteModal && (
                  <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-gray-800 border border-gray-700 rounded-2xl p-6 w-full max-w-md">
                      <h3 className="text-lg font-semibold mb-4">Inviter un membre</h3>
                      <form onSubmit={handleInvite} className="space-y-4">
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Email *</label>
                          <input
                            type="email"
                            value={inviteForm.email}
                            onChange={(e) => setInviteForm(p => ({ ...p, email: e.target.value }))}
                            className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white"
                            required
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-sm text-gray-400 mb-2">Prénom</label>
                            <input
                              type="text"
                              value={inviteForm.first_name}
                              onChange={(e) => setInviteForm(p => ({ ...p, first_name: e.target.value }))}
                              className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white"
                            />
                          </div>
                          <div>
                            <label className="block text-sm text-gray-400 mb-2">Nom</label>
                            <input
                              type="text"
                              value={inviteForm.last_name}
                              onChange={(e) => setInviteForm(p => ({ ...p, last_name: e.target.value }))}
                              className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white"
                            />
                          </div>
                        </div>
                        <div>
                          <label className="block text-sm text-gray-400 mb-2">Rôle</label>
                          <select
                            value={inviteForm.role}
                            onChange={(e) => setInviteForm(p => ({ ...p, role: e.target.value }))}
                            className="w-full px-4 py-2 bg-gray-700/50 border border-gray-600 rounded-lg text-white"
                          >
                            <option value="member">Membre</option>
                            <option value="manager">Manager</option>
                            <option value="admin">Administrateur</option>
                            <option value="viewer">Lecteur seul</option>
                          </select>
                        </div>
                        <div className="flex justify-end space-x-3 pt-4">
                          <button
                            type="button"
                            onClick={() => setShowInviteModal(false)}
                            className="px-4 py-2 border border-gray-600 rounded-lg hover:bg-gray-700 transition-colors"
                          >
                            Annuler
                          </button>
                          <button
                            type="submit"
                            disabled={isLoading}
                            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors disabled:opacity-50"
                          >
                            {isLoading ? 'Envoi...' : 'Inviter'}
                          </button>
                        </div>
                      </form>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Billing Tab */}
            {activeTab === 'billing' && tenant && (
              <div>
                <h2 className="text-lg font-semibold mb-6">Facturation & Usage</h2>

                {/* Plan */}
                <div className="mb-8 p-6 bg-gradient-to-r from-blue-600/20 to-purple-600/20 border border-blue-500/30 rounded-xl">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm text-gray-400 mb-1">Plan actuel</div>
                      <div className="text-2xl font-bold">{planLabels[tenant.plan]?.name || tenant.plan}</div>
                      <div className="text-sm text-gray-400 mt-1">
                        {tenant.subscription_status === 'trial' && '🎁 Période d\'essai'}
                        {tenant.subscription_status === 'active' && '✅ Actif'}
                      </div>
                    </div>
                    <button className="px-4 py-2 bg-gradient-to-r from-amber-500 to-amber-400 text-gray-900 font-medium rounded-lg hover:from-amber-400 hover:to-amber-300 transition-all">
                      Upgrader
                    </button>
                  </div>
                </div>

                {/* Usage Stats */}
                {usageStats && (
                  <div className="mb-8">
                    <h3 className="text-md font-semibold mb-4">Usage du mois ({usageStats.current_period})</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-4 bg-gray-700/30 border border-gray-600 rounded-lg">
                        <div className="text-sm text-gray-400">Exécutions</div>
                        <div className="text-2xl font-bold">
                          {usageStats.workflow_executions + usageStats.agent_calls}
                          <span className="text-sm text-gray-400 font-normal">
                            /{usageStats.limits.max_executions_per_month}
                          </span>
                        </div>
                        <div className="mt-2 h-2 bg-gray-600 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-blue-500 rounded-full"
                            style={{ width: `${Math.min(usageStats.usage_percentage.executions, 100)}%` }}
                          />
                        </div>
                      </div>
                      <div className="p-4 bg-gray-700/30 border border-gray-600 rounded-lg">
                        <div className="text-sm text-gray-400">Appels MCP</div>
                        <div className="text-2xl font-bold">{usageStats.mcp_tool_calls}</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Limits */}
                <div>
                  <h3 className="text-md font-semibold mb-4">Limites de votre plan</h3>
                  <div className="grid grid-cols-4 gap-4">
                    {[
                      { label: 'Utilisateurs', value: tenant.max_users },
                      { label: 'Agents', value: tenant.max_agents },
                      { label: 'Workflows', value: tenant.max_workflows },
                      { label: 'Exécutions/mois', value: tenant.max_executions_per_month },
                    ].map((limit) => (
                      <div key={limit.label} className="p-4 bg-gray-700/30 border border-gray-600 rounded-lg text-center">
                        <div className="text-2xl font-bold">{limit.value}</div>
                        <div className="text-sm text-gray-400">{limit.label}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
