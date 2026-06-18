import { 
  LoginRequest, 
  LoginResponse, 
  RefreshTokenRequest, 
  RefreshTokenResponse, 
  RegisterRequest,
  ResetPasswordRequest,
  ChangePasswordRequest,
  AuthUser 
} from './types';
import { get, post, put } from '@/lib/api/client';

/**
 * Authentication API client
 */
export const authApi = {
  // Login with email and password
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    return post<LoginResponse, LoginRequest>('/api/auth/login', credentials);
  },

  // Logout (server-side token invalidation)
  async logout(): Promise<void> {
    return post<void>('/api/auth/logout');
  },

  // Refresh access token
  async refreshToken(data: RefreshTokenRequest): Promise<RefreshTokenResponse> {
    return post<RefreshTokenResponse, RefreshTokenRequest>('/api/auth/refresh', data);
  },

  // Get current user profile
  async getCurrentUser(): Promise<AuthUser> {
    return get<AuthUser>('/api/auth/me');
  },

  // Register new user
  async register(data: RegisterRequest): Promise<LoginResponse> {
    return post<LoginResponse, RegisterRequest>('/api/auth/register', data);
  },

  // Update user profile
  async updateProfile(data: Partial<AuthUser>): Promise<AuthUser> {
    return put<AuthUser>('/api/auth/profile', data);
  },

  // Change password
  async changePassword(data: ChangePasswordRequest): Promise<void> {
    return put<void>('/api/auth/password', data);
  },

  // Request password reset
  async requestPasswordReset(data: ResetPasswordRequest): Promise<void> {
    return post<void>('/api/auth/forgot-password', data);
  },

  // Verify email (if email verification is enabled)
  async verifyEmail(token: string): Promise<void> {
    return post<void>(`/api/auth/verify-email/${token}`);
  },

  // Resend verification email
  async resendVerificationEmail(): Promise<void> {
    return post<void>('/api/auth/resend-verification');
  },

  // Check if email is available for registration
  async checkEmailAvailability(email: string): Promise<{ available: boolean }> {
    return get<{ available: boolean }>('/api/auth/check-email', { email });
  },

  // Get user sessions (if session management is implemented)
  async getSessions(): Promise<Array<{
    id: string;
    device: string;
    location: string;
    last_active: string;
    is_current: boolean;
  }>> {
    return get('/api/auth/sessions');
  },

  // Revoke session
  async revokeSession(sessionId: string): Promise<void> {
    return post<void>(`/api/auth/sessions/${sessionId}/revoke`);
  },

  // Revoke all sessions except current
  async revokeAllSessions(): Promise<void> {
    return post<void>('/api/auth/sessions/revoke-all');
  },
};

export default authApi;