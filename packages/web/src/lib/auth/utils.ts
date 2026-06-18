import Cookies from 'js-cookie';
import { jwtDecode } from 'jwt-decode';
import { AuthUser, TokenInfo, StoredAuth, SessionConfig } from './types';

// Session configuration
export const SESSION_CONFIG: SessionConfig = {
  tokenStorageKey: 'auth_token',
  refreshTokenStorageKey: 'refresh_token',
  userStorageKey: 'auth_user',
  sessionTimeout: 60, // 1 hour
  refreshThreshold: 5, // Refresh 5 minutes before expiry
  rememberMeDuration: 30, // 30 days
};

// Storage utilities
export const storage = {
  // Token storage (prefer httpOnly cookies for security)
  setToken: (token: string, rememberMe = false): void => {
    if (typeof window === 'undefined') return;
    
    const expires = rememberMe ? SESSION_CONFIG.rememberMeDuration : undefined;
    
    // Use secure cookies in production
    const cookieOptions = {
      expires,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax' as const,
    };
    
    Cookies.set(SESSION_CONFIG.tokenStorageKey, token, cookieOptions);
  },

  getToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return Cookies.get(SESSION_CONFIG.tokenStorageKey) || null;
  },

  removeToken: (): void => {
    if (typeof window === 'undefined') return;
    Cookies.remove(SESSION_CONFIG.tokenStorageKey);
  },

  // Refresh token storage
  setRefreshToken: (token: string, rememberMe = false): void => {
    if (typeof window === 'undefined') return;
    
    const expires = rememberMe ? SESSION_CONFIG.rememberMeDuration : undefined;
    
    const cookieOptions = {
      expires,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax' as const,
      httpOnly: false, // Needs to be accessible to JS for refresh
    };
    
    Cookies.set(SESSION_CONFIG.refreshTokenStorageKey, token, cookieOptions);
  },

  getRefreshToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return Cookies.get(SESSION_CONFIG.refreshTokenStorageKey) || null;
  },

  removeRefreshToken: (): void => {
    if (typeof window === 'undefined') return;
    Cookies.remove(SESSION_CONFIG.refreshTokenStorageKey);
  },

  // User data storage (localStorage for non-sensitive data)
  setUser: (user: AuthUser): void => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(SESSION_CONFIG.userStorageKey, JSON.stringify(user));
  },

  getUser: (): AuthUser | null => {
    if (typeof window === 'undefined') return null;
    
    try {
      const userData = localStorage.getItem(SESSION_CONFIG.userStorageKey);
      return userData ? JSON.parse(userData) : null;
    } catch {
      return null;
    }
  },

  removeUser: (): void => {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(SESSION_CONFIG.userStorageKey);
  },

  // Complete auth data management
  setAuth: (token: string, user: AuthUser, refreshToken?: string, rememberMe = false): void => {
    storage.setToken(token, rememberMe);
    storage.setUser(user);
    if (refreshToken) {
      storage.setRefreshToken(refreshToken, rememberMe);
    }
  },

  getAuth: (): StoredAuth | null => {
    const token = storage.getToken();
    const user = storage.getUser();
    
    if (!token || !user) return null;
    
    const tokenInfo = parseToken(token);
    
    return {
      token,
      refreshToken: storage.getRefreshToken() || undefined,
      user,
      expiresAt: tokenInfo.expiresAt,
    };
  },

  clearAuth: (): void => {
    storage.removeToken();
    storage.removeUser();
    storage.removeRefreshToken();
  },
};

// Token utilities
export const parseToken = (token: string): TokenInfo => {
  try {
    const decoded = jwtDecode<{ exp: number; iat: number }>(token);
    const expiresAt = decoded.exp * 1000; // Convert to milliseconds
    const now = Date.now();
    
    return {
      token,
      expiresAt,
      isExpired: now >= expiresAt,
      timeUntilExpiry: Math.max(0, expiresAt - now),
    };
  } catch {
    // If token is invalid, treat as expired
    return {
      token,
      expiresAt: 0,
      isExpired: true,
      timeUntilExpiry: 0,
    };
  }
};

export const isTokenExpired = (token: string): boolean => {
  return parseToken(token).isExpired;
};

export const shouldRefreshToken = (token: string): boolean => {
  const tokenInfo = parseToken(token);
  const thresholdMs = SESSION_CONFIG.refreshThreshold * 60 * 1000; // Convert to milliseconds
  
  return !tokenInfo.isExpired && tokenInfo.timeUntilExpiry <= thresholdMs;
};

// Auth validation utilities
export const validateEmail = (email: string): boolean => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

export const validatePassword = (password: string): { isValid: boolean; errors: string[] } => {
  const errors: string[] = [];
  
  if (password.length < 8) {
    errors.push('Password must be at least 8 characters long');
  }
  
  if (!/(?=.*[a-z])/.test(password)) {
    errors.push('Password must contain at least one lowercase letter');
  }
  
  if (!/(?=.*[A-Z])/.test(password)) {
    errors.push('Password must contain at least one uppercase letter');
  }
  
  if (!/(?=.*\d)/.test(password)) {
    errors.push('Password must contain at least one number');
  }
  
  return {
    isValid: errors.length === 0,
    errors,
  };
};

// Cross-tab synchronization
export const createStorageListener = (callback: () => void): (() => void) => {
  if (typeof window === 'undefined') return () => {};
  
  const handleStorageChange = (e: StorageEvent) => {
    // Detect changes to auth-related storage
    if (
      e.key === SESSION_CONFIG.userStorageKey ||
      e.key === null // Clear all
    ) {
      callback();
    }
  };
  
  // Listen for storage changes (logout in other tabs)
  window.addEventListener('storage', handleStorageChange);
  
  // Return cleanup function
  return () => {
    window.removeEventListener('storage', handleStorageChange);
  };
};

// URL utilities for redirects
export const getReturnUrl = (): string => {
  if (typeof window === 'undefined') return '/dashboard';
  
  const params = new URLSearchParams(window.location.search);
  return params.get('returnUrl') || '/dashboard';
};

export const setReturnUrl = (url: string): void => {
  if (typeof window === 'undefined') return;
  
  const currentUrl = new URL(window.location.href);
  currentUrl.searchParams.set('returnUrl', url);
  window.history.replaceState({}, '', currentUrl.toString());
};

export const clearReturnUrl = (): void => {
  if (typeof window === 'undefined') return;
  
  const currentUrl = new URL(window.location.href);
  currentUrl.searchParams.delete('returnUrl');
  window.history.replaceState({}, '', currentUrl.toString());
};

// Error utilities
export const getAuthErrorMessage = (error: any): string => {
  if (typeof error === 'string') return error;
  
  if (error?.response?.data?.detail) {
    return error.response.data.detail;
  }
  
  if (error?.message) {
    return error.message;
  }
  
  return 'An unexpected error occurred';
};

// Development utilities
export const isDevelopment = (): boolean => {
  return process.env.NODE_ENV === 'development';
};

export const debugAuth = (message: string, data?: any): void => {
  if (isDevelopment()) {
    console.log(`[Auth Debug] ${message}`, data);
  }
};