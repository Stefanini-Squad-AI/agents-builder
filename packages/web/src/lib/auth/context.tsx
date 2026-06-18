"use client"

import React, { createContext, useContext, useEffect, useReducer, useCallback, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { 
  AuthContextType, 
  AuthState, 
  AuthUser, 
  LoginRequest, 
  RegisterRequest,
  AuthError,
  TokenExpiredError,
  InvalidCredentialsError,
  NetworkError 
} from './types';
import { authApi } from './client';
import { 
  storage, 
  parseToken, 
  shouldRefreshToken, 
  isTokenExpired,
  createStorageListener,
  debugAuth,
  getAuthErrorMessage 
} from './utils';
import { UserRole } from '@/lib/api/types';

// Auth state actions
type AuthAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_USER'; payload: AuthUser | null }
  | { type: 'SET_TOKEN'; payload: { token: string | null; refreshToken?: string | null } }
  | { type: 'SET_INITIALIZED'; payload: boolean }
  | { type: 'LOGOUT' }
  | { type: 'RESTORE_SESSION'; payload: { user: AuthUser; token: string; refreshToken?: string } };

// Initial auth state
const initialState: AuthState = {
  user: null,
  token: null,
  refreshToken: null,
  isLoading: false,
  isAuthenticated: false,
  isInitialized: false,
};

// Auth reducer
function authReducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    
    case 'SET_USER':
      return { 
        ...state, 
        user: action.payload,
        isAuthenticated: action.payload !== null,
      };
    
    case 'SET_TOKEN':
      return { 
        ...state, 
        token: action.payload.token,
        refreshToken: action.payload.refreshToken || state.refreshToken,
      };
    
    case 'SET_INITIALIZED':
      return { ...state, isInitialized: action.payload };
    
    case 'RESTORE_SESSION':
      return {
        ...state,
        user: action.payload.user,
        token: action.payload.token,
        refreshToken: action.payload.refreshToken || null,
        isAuthenticated: true,
        isInitialized: true,
      };
    
    case 'LOGOUT':
      return {
        ...initialState,
        isInitialized: true,
      };
    
    default:
      return state;
  }
}

// Create context
const AuthContext = createContext<AuthContextType | null>(null);

// Auth provider component
interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, dispatch] = useReducer(authReducer, initialState);
  const queryClient = useQueryClient();
  const refreshPromiseRef = useRef<Promise<boolean> | null>(null);

  // Initialize auth state on mount
  useEffect(() => {
    initializeAuth();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Set up cross-tab synchronization
  useEffect(() => {
    const cleanup = createStorageListener(() => {
      debugAuth('Storage change detected, re-initializing auth');
      initializeAuth();
    });

    return cleanup;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Set up automatic token refresh
  useEffect(() => {
    if (state.token && state.isAuthenticated) {
      const interval = setInterval(() => {
        if (shouldRefreshToken(state.token!)) {
          debugAuth('Token needs refresh, attempting automatic refresh');
          refreshToken();
        }
      }, 60000); // Check every minute

      return () => clearInterval(interval);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.token, state.isAuthenticated]);

  const initializeAuth = useCallback(async () => {
    dispatch({ type: 'SET_LOADING', payload: true });

    try {
      const storedAuth = storage.getAuth();
      
      if (!storedAuth) {
        debugAuth('No stored auth found');
        dispatch({ type: 'SET_INITIALIZED', payload: true });
        dispatch({ type: 'SET_LOADING', payload: false });
        return;
      }

      const { token, user, refreshToken: storedRefreshToken } = storedAuth;

      if (isTokenExpired(token)) {
        debugAuth('Stored token is expired');
        
        if (storedRefreshToken) {
          debugAuth('Attempting to refresh expired token');
          const refreshSuccess = await refreshTokenInternal(storedRefreshToken);
          
          if (!refreshSuccess) {
            debugAuth('Token refresh failed, clearing auth');
            storage.clearAuth();
            dispatch({ type: 'LOGOUT' });
          }
        } else {
          debugAuth('No refresh token, clearing auth');
          storage.clearAuth();
          dispatch({ type: 'LOGOUT' });
        }
      } else {
        debugAuth('Restoring valid session');
        dispatch({ 
          type: 'RESTORE_SESSION', 
          payload: { user, token, refreshToken: storedRefreshToken } 
        });
      }
    } catch (error) {
      debugAuth('Error initializing auth:', error);
      storage.clearAuth();
      dispatch({ type: 'LOGOUT' });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (credentials: LoginRequest) => {
    dispatch({ type: 'SET_LOADING', payload: true });

    try {
      const response = await authApi.login(credentials);
      const { access_token, refresh_token, user } = response;

      // Store auth data
      storage.setAuth(access_token, user, refresh_token, credentials.remember_me);

      // Update state
      dispatch({ type: 'SET_USER', payload: user });
      dispatch({ type: 'SET_TOKEN', payload: { token: access_token, refreshToken: refresh_token } });

      debugAuth('Login successful', { user: user.email });

    } catch (error: any) {
      debugAuth('Login failed:', error);
      
      // Convert to user-friendly errors
      if (error?.response?.status === 401) {
        throw new InvalidCredentialsError();
      } else if (error?.code === 'NETWORK_ERROR') {
        throw new NetworkError();
      } else {
        throw new AuthError(getAuthErrorMessage(error), 'LOGIN_FAILED');
      }
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, []);

  const logout = useCallback(async () => {
    dispatch({ type: 'SET_LOADING', payload: true });

    try {
      // Attempt server-side logout
      if (state.token) {
        await authApi.logout();
      }
    } catch (error) {
      // Continue with logout even if server call fails
      debugAuth('Server logout failed:', error);
    } finally {
      // Clear local storage and state
      storage.clearAuth();
      dispatch({ type: 'LOGOUT' });
      
      // Clear all cached queries
      queryClient.clear();
      
      debugAuth('Logout completed');
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.token, queryClient]);

  const register = useCallback(async (data: RegisterRequest) => {
    dispatch({ type: 'SET_LOADING', payload: true });

    try {
      const response = await authApi.register(data);
      const { access_token, refresh_token, user } = response;

      // Store auth data
      storage.setAuth(access_token, user, refresh_token);

      // Update state
      dispatch({ type: 'SET_USER', payload: user });
      dispatch({ type: 'SET_TOKEN', payload: { token: access_token, refreshToken: refresh_token } });

      debugAuth('Registration successful', { user: user.email });

    } catch (error: any) {
      debugAuth('Registration failed:', error);
      
      if (error?.response?.status === 400) {
        throw new AuthError(getAuthErrorMessage(error), 'REGISTRATION_FAILED', 400);
      } else if (error?.code === 'NETWORK_ERROR') {
        throw new NetworkError();
      } else {
        throw new AuthError(getAuthErrorMessage(error), 'REGISTRATION_FAILED');
      }
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, []);

  const refreshTokenInternal = useCallback(async (refreshTokenParam?: string): Promise<boolean> => {
    const refreshTokenToUse = refreshTokenParam || state.refreshToken;
    
    if (!refreshTokenToUse) {
      debugAuth('No refresh token available');
      return false;
    }

    try {
      const response = await authApi.refreshToken({ refresh_token: refreshTokenToUse });
      const { access_token, refresh_token: new_refresh_token } = response;

      // Update stored tokens
      const currentUser = state.user || storage.getUser();
      if (currentUser) {
        storage.setAuth(access_token, currentUser, new_refresh_token || refreshTokenToUse);
      }

      // Update state
      dispatch({ 
        type: 'SET_TOKEN', 
        payload: { token: access_token, refreshToken: new_refresh_token || refreshTokenToUse } 
      });

      debugAuth('Token refresh successful');
      return true;

    } catch (error) {
      debugAuth('Token refresh failed:', error);
      return false;
    }
  }, [state.refreshToken, state.user]);

  const refreshToken = useCallback(async (): Promise<boolean> => {
    // Prevent concurrent refresh requests
    if (refreshPromiseRef.current) {
      return refreshPromiseRef.current;
    }

    refreshPromiseRef.current = refreshTokenInternal();
    
    try {
      const result = await refreshPromiseRef.current;
      return result;
    } finally {
      refreshPromiseRef.current = null;
    }
  }, [refreshTokenInternal]);

  const updateProfile = useCallback(async (data: Partial<AuthUser>) => {
    if (!state.user) return;

    dispatch({ type: 'SET_LOADING', payload: true });

    try {
      const updatedUser = await authApi.updateProfile(data);
      
      // Update stored user data
      storage.setUser(updatedUser);
      
      // Update state
      dispatch({ type: 'SET_USER', payload: updatedUser });

      debugAuth('Profile updated successfully');

    } catch (error) {
      debugAuth('Profile update failed:', error);
      throw new AuthError(getAuthErrorMessage(error), 'PROFILE_UPDATE_FAILED');
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.user]);

  // Utility functions
  const hasRole = useCallback((role: UserRole): boolean => {
    return state.user?.role === role;
  }, [state.user]);

  const canAccess = useCallback((resource: string, action?: string): boolean => {
    if (!state.user) return false;

    // Basic role-based access control
    switch (state.user.role) {
      case UserRole.OWNER:
        return true; // Owners can access everything
      
      case UserRole.MEMBER:
        // Members can access most resources but not admin functions
        return !resource.includes('admin') && action !== 'delete';
      
      case UserRole.READONLY:
        // Readonly users can only read
        return action === 'read' || action === undefined;
      
      default:
        return false;
    }
  }, [state.user]);

  const contextValue: AuthContextType = {
    // State
    user: state.user,
    isLoading: state.isLoading,
    isAuthenticated: state.isAuthenticated,
    isInitialized: state.isInitialized,

    // Actions
    login,
    logout,
    register,
    refreshToken,
    updateProfile,

    // Utilities
    hasRole,
    canAccess,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}

// Hook to use auth context
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  
  return context;
}

export { AuthContext };