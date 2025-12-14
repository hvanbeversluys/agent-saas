"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

// Types
interface User {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string;
  avatar_url: string | null;
  job_title: string | null;
  role: string;
  is_active: boolean;
  email_verified: boolean;
}

interface Tenant {
  id: string;
  name: string;
  slug: string;
  email: string;
  logo_url: string | null;
  primary_color: string;
  plan: string;
  subscription_status: string;
  max_users: number;
  max_agents: number;
  max_workflows: number;
  max_executions_per_month: number;
}

interface AuthState {
  user: User | null;
  tenant: Tenant | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  updateUser: (data: Partial<User>) => Promise<void>;
  refreshToken: () => Promise<void>;
}

interface RegisterData {
  email: string;
  password: string;
  company_name: string;
  first_name?: string;
  last_name?: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  tenant: Tenant;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Storage helpers
const getStoredTokens = () => {
  if (typeof window === 'undefined') return null;
  const access = localStorage.getItem('access_token');
  const refresh = localStorage.getItem('refresh_token');
  return access && refresh ? { access, refresh } : null;
};

const setStoredTokens = (access: string, refresh: string) => {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
};

const clearStoredTokens = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    tenant: null,
    isAuthenticated: false,
    isLoading: true,
  });

  // Fetch user on mount
  useEffect(() => {
    const initAuth = async () => {
      const tokens = getStoredTokens();
      if (!tokens) {
        setState(prev => ({ ...prev, isLoading: false }));
        return;
      }

      try {
        const response = await fetch(`${API_URL}/api/auth/me`, {
          headers: {
            'Authorization': `Bearer ${tokens.access}`,
          },
        });

        if (response.ok) {
          const user = await response.json();
          
          // Fetch tenant info
          const tenantResponse = await fetch(`${API_URL}/api/tenant`, {
            headers: {
              'Authorization': `Bearer ${tokens.access}`,
            },
          });
          
          const tenant = tenantResponse.ok ? await tenantResponse.json() : null;

          setState({
            user,
            tenant,
            isAuthenticated: true,
            isLoading: false,
          });
        } else if (response.status === 401) {
          // Try to refresh token
          try {
            await refreshTokenInternal(tokens.refresh);
          } catch {
            clearStoredTokens();
            setState({
              user: null,
              tenant: null,
              isAuthenticated: false,
              isLoading: false,
            });
          }
        } else {
          clearStoredTokens();
          setState({
            user: null,
            tenant: null,
            isAuthenticated: false,
            isLoading: false,
          });
        }
      } catch (error) {
        console.error('Auth init error:', error);
        clearStoredTokens();
        setState({
          user: null,
          tenant: null,
          isAuthenticated: false,
          isLoading: false,
        });
      }
    };

    initAuth();
  }, []);

  const refreshTokenInternal = async (refreshToken: string) => {
    const response = await fetch(`${API_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      throw new Error('Refresh failed');
    }

    const data: TokenResponse = await response.json();
    setStoredTokens(data.access_token, data.refresh_token);
    
    setState({
      user: data.user,
      tenant: data.tenant,
      isAuthenticated: true,
      isLoading: false,
    });
  };

  const login = async (email: string, password: string) => {
    const response = await fetch(`${API_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Erreur de connexion');
    }

    const data: TokenResponse = await response.json();
    setStoredTokens(data.access_token, data.refresh_token);

    setState({
      user: data.user,
      tenant: data.tenant,
      isAuthenticated: true,
      isLoading: false,
    });
  };

  const register = async (data: RegisterData) => {
    const response = await fetch(`${API_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Erreur lors de l\'inscription');
    }

    const result: TokenResponse = await response.json();
    setStoredTokens(result.access_token, result.refresh_token);

    setState({
      user: result.user,
      tenant: result.tenant,
      isAuthenticated: true,
      isLoading: false,
    });
  };

  const logout = async () => {
    const tokens = getStoredTokens();
    if (tokens) {
      try {
        await fetch(`${API_URL}/api/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${tokens.access}`,
          },
        });
      } catch (error) {
        console.error('Logout error:', error);
      }
    }

    clearStoredTokens();
    setState({
      user: null,
      tenant: null,
      isAuthenticated: false,
      isLoading: false,
    });
  };

  const updateUser = async (data: Partial<User>) => {
    const tokens = getStoredTokens();
    if (!tokens) throw new Error('Non authentifié');

    const response = await fetch(`${API_URL}/api/auth/me`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${tokens.access}`,
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Erreur lors de la mise à jour');
    }

    const updatedUser = await response.json();
    setState(prev => ({ ...prev, user: updatedUser }));
  };

  const refreshToken = async () => {
    const tokens = getStoredTokens();
    if (!tokens) throw new Error('Non authentifié');
    await refreshTokenInternal(tokens.refresh);
  };

  return (
    <AuthContext.Provider value={{
      ...state,
      login,
      register,
      logout,
      updateUser,
      refreshToken,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Hook pour les appels API authentifiés
export function useAuthFetch() {
  const { isAuthenticated } = useAuth();

  const authFetch = async (url: string, options: RequestInit = {}) => {
    const tokens = getStoredTokens();
    
    const headers = new Headers(options.headers);
    if (tokens) {
      headers.set('Authorization', `Bearer ${tokens.access}`);
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    // Si 401, on pourrait tenter un refresh ici
    if (response.status === 401 && isAuthenticated) {
      // Token expiré - on devrait rediriger vers login
      clearStoredTokens();
      window.location.href = '/login';
    }

    return response;
  };

  return authFetch;
}
