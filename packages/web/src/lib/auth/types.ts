import { UserRole } from '@/lib/api/types';

// Core auth types
export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  tenant_id: string;
  tenant_name: string;
  created_at: string;
}

export interface AuthState {
  user: AuthUser | null;
  token: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isInitialized: boolean;
}

// Auth API request/response types
export interface LoginRequest {
  email: string;
  password: string;
  remember_me?: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface RefreshTokenResponse {
  access_token: string;
  refresh_token?: string;
  expires_in: number;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  tenant_name?: string;
}

export interface ResetPasswordRequest {
  email: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

// Auth context types
export interface AuthContextType {
  // State
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isInitialized: boolean;
  
  // Actions
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  refreshToken: () => Promise<boolean>;
  updateProfile: (data: Partial<AuthUser>) => Promise<void>;
  
  // Utilities
  hasRole: (role: UserRole) => boolean;
  canAccess: (resource: string, action?: string) => boolean;
}

// Token management types
export interface TokenInfo {
  token: string;
  expiresAt: number;
  isExpired: boolean;
  timeUntilExpiry: number;
}

export interface StoredAuth {
  token: string;
  refreshToken?: string;
  user: AuthUser;
  expiresAt: number;
}

// Auth error types
export class AuthError extends Error {
  constructor(
    message: string,
    public code: string,
    public statusCode?: number
  ) {
    super(message);
    this.name = 'AuthError';
  }
}

export class TokenExpiredError extends AuthError {
  constructor() {
    super('Token has expired', 'TOKEN_EXPIRED', 401);
  }
}

export class InvalidCredentialsError extends AuthError {
  constructor() {
    super('Invalid email or password', 'INVALID_CREDENTIALS', 401);
  }
}

export class NetworkError extends AuthError {
  constructor() {
    super('Network error occurred', 'NETWORK_ERROR', 0);
  }
}

// Route protection types
export interface RouteConfig {
  path: string;
  requireAuth: boolean;
  allowedRoles?: UserRole[];
  redirectTo?: string;
}

export type AuthRedirect = {
  type: 'login' | 'unauthorized' | 'dashboard';
  returnUrl?: string;
};

// Session management types
export interface SessionConfig {
  tokenStorageKey: string;
  refreshTokenStorageKey: string;
  userStorageKey: string;
  sessionTimeout: number; // in minutes
  refreshThreshold: number; // in minutes before expiry
  rememberMeDuration: number; // in days
}