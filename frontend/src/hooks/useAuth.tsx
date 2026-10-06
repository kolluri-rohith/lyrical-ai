import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import * as api from '../services/api';
import type { AuthResponse, User } from '../types';
import { clearToken, getToken, setToken } from '../utils/clientId';

interface AuthContextValue {
  user: User | null;
  /** True while a stored session is being restored. */
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(() => Boolean(getToken()));

  useEffect(() => {
    if (!getToken()) return;
    let active = true;
    api
      .fetchMe()
      .then((me) => {
        if (active) setUser(me);
      })
      .catch(() => {
        // A 401 already cleared the token; other failures just leave the user signed out for now.
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const onUnauthorized = () => setUser(null);
    window.addEventListener(api.UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(api.UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const applySession = useCallback((session: AuthResponse) => {
    setToken(session.accessToken);
    setUser(session.user);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => applySession(await api.login(email, password)),
    [applySession],
  );

  const register = useCallback(
    async (name: string, email: string, password: string) =>
      applySession(await api.register(name, email, password)),
    [applySession],
  );

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>');
  return context;
}
