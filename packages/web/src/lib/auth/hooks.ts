import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useEffect, useCallback, useState } from 'react';
import { useAuth } from './context';
import { authApi } from './client';
import { AuthUser, ChangePasswordRequest, ResetPasswordRequest } from './types';
import { getReturnUrl, clearReturnUrl, debugAuth } from './utils';

/**
 * Hook for current user profile with React Query
 */
export function useCurrentUser() {
  const { isAuthenticated } = useAuth();
  
  return useQuery({
    queryKey: ['auth', 'currentUser'],
    queryFn: () => authApi.getCurrentUser(),
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: (failureCount, error: any) => {
      // Don't retry on 401 errors (token expired)
      if (error?.response?.status === 401) {
        return false;
      }
      return failureCount < 2;
    },
  });
}

/**
 * Hook for profile update mutation
 */
export function useUpdateProfile() {
  const queryClient = useQueryClient();
  const { updateProfile } = useAuth();
  
  return useMutation({
    mutationFn: (data: Partial<AuthUser>) => updateProfile(data),
    onSuccess: (updatedUser) => {
      // Update the current user query cache
      queryClient.setQueryData(['auth', 'currentUser'], updatedUser);
    },
    onError: (error) => {
      debugAuth('Profile update mutation failed:', error);
    },
  });
}

/**
 * Hook for password change mutation
 */
export function useChangePassword() {
  return useMutation({
    mutationFn: (data: ChangePasswordRequest) => authApi.changePassword(data),
    onError: (error) => {
      debugAuth('Password change failed:', error);
    },
  });
}

/**
 * Hook for password reset request
 */
export function useResetPassword() {
  return useMutation({
    mutationFn: (data: ResetPasswordRequest) => authApi.requestPasswordReset(data),
    onError: (error) => {
      debugAuth('Password reset request failed:', error);
    },
  });
}

/**
 * Hook for email availability check
 */
export function useCheckEmailAvailability(email: string, enabled = true) {
  return useQuery({
    queryKey: ['auth', 'checkEmail', email],
    queryFn: () => authApi.checkEmailAvailability(email),
    enabled: enabled && !!email && email.includes('@'),
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Hook for user sessions management
 */
export function useUserSessions() {
  const { isAuthenticated } = useAuth();
  
  return useQuery({
    queryKey: ['auth', 'sessions'],
    queryFn: () => authApi.getSessions(),
    enabled: isAuthenticated,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

/**
 * Hook for revoking sessions
 */
export function useRevokeSession() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (sessionId: string) => authApi.revokeSession(sessionId),
    onSuccess: () => {
      // Invalidate sessions query
      queryClient.invalidateQueries({ queryKey: ['auth', 'sessions'] });
    },
  });
}

/**
 * Hook for login with redirect handling
 */
export function useLoginWithRedirect() {
  const { login } = useAuth();
  const router = useRouter();
  
  return useMutation({
    mutationFn: login,
    onSuccess: () => {
      // Redirect to intended page or dashboard
      const returnUrl = getReturnUrl();
      clearReturnUrl();
      
      debugAuth('Login successful, redirecting to:', returnUrl);
      router.push(returnUrl as any);
    },
  });
}

/**
 * Hook for logout with redirect
 */
export function useLogoutWithRedirect() {
  const { logout } = useAuth();
  const router = useRouter();
  
  return useMutation({
    mutationFn: logout,
    onSuccess: () => {
      debugAuth('Logout successful, redirecting to login');
      router.push('/login');
    },
  });
}

/**
 * Hook for route protection
 */
export function useRouteProtection(requireAuth = true, allowedRoles?: string[]) {
  const { isAuthenticated, isLoading, isInitialized, user, canAccess } = useAuth();
  const router = useRouter();
  const [shouldRender, setShouldRender] = useState(false);

  useEffect(() => {
    if (!isInitialized) {
      setShouldRender(false);
      return;
    }

    if (requireAuth && !isAuthenticated) {
      debugAuth('Route requires auth, redirecting to login');
      router.push('/login' as any);
      setShouldRender(false);
      return;
    }

    if (allowedRoles && user && !allowedRoles.includes(user.role)) {
      debugAuth('User does not have required role, access denied');
      router.push('/' as any); // Redirect to home instead of unauthorized page
      setShouldRender(false);
      return;
    }

    setShouldRender(true);
  }, [isAuthenticated, isInitialized, isLoading, user, requireAuth, allowedRoles, router]);

  return {
    shouldRender,
    isLoading: !isInitialized || isLoading,
    canAccess,
  };
}

/**
 * Hook for auth-aware navigation
 */
export function useAuthNavigation() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  const navigateToLogin = useCallback((returnUrl?: string) => {
    const loginUrl = returnUrl ? `/login?returnUrl=${encodeURIComponent(returnUrl)}` : '/login';
    router.push(loginUrl as any);
  }, [router]);

  const navigateToDashboard = useCallback(() => {
    router.push('/dashboard' as any);
  }, [router]);

  const navigateToProfile = useCallback(() => {
    router.push('/profile' as any);
  }, [router]);

  return {
    isAuthenticated,
    isLoading,
    navigateToLogin,
    navigateToDashboard,
    navigateToProfile,
  };
}

/**
 * Hook for form state management with auth
 */
export function useAuthForm<T extends Record<string, any>>(initialValues: T) {
  const [values, setValues] = useState<T>(initialValues);
  const [errors, setErrors] = useState<Partial<Record<keyof T, string>>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const setValue = useCallback((field: keyof T, value: any) => {
    setValues(prev => ({ ...prev, [field]: value }));
    
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
  }, [errors]);

  const setError = useCallback((field: keyof T, error: string) => {
    setErrors(prev => ({ ...prev, [field]: error }));
  }, []);

  const clearErrors = useCallback(() => {
    setErrors({});
  }, []);

  const reset = useCallback(() => {
    setValues(initialValues);
    setErrors({});
    setIsSubmitting(false);
  }, [initialValues]);

  return {
    values,
    errors,
    isSubmitting,
    setValue,
    setError,
    clearErrors,
    reset,
    setIsSubmitting,
  };
}

/**
 * Hook for session timeout warning
 */
export function useSessionTimeout(warningMinutes = 5) {
  const { isAuthenticated, refreshToken } = useAuth();
  const [showWarning, setShowWarning] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);

  useEffect(() => {
    if (!isAuthenticated) {
      setShowWarning(false);
      return;
    }

    // This would need to track token expiration time
    // Implementation depends on token structure and refresh logic
    
    // Placeholder for session timeout logic
    const checkSession = () => {
      // Check if session is close to expiring
      // Show warning if within warningMinutes
    };

    const interval = setInterval(checkSession, 30000); // Check every 30 seconds
    
    return () => clearInterval(interval);
  }, [isAuthenticated, warningMinutes]);

  const extendSession = useCallback(async () => {
    try {
      await refreshToken();
      setShowWarning(false);
      debugAuth('Session extended successfully');
    } catch (error) {
      debugAuth('Failed to extend session:', error);
    }
  }, [refreshToken]);

  return {
    showWarning,
    timeLeft,
    extendSession,
  };
}