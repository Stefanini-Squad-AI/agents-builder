"use client"

import { useAuth } from '@/lib/auth/context';
import { UserMenu, LoginButton } from './user-menu';

export function HeaderAuth() {
  const { isAuthenticated, isLoading, isInitialized } = useAuth();

  // Don't show anything while auth is initializing
  if (!isInitialized) {
    return (
      <div className="h-9 w-9 animate-pulse bg-muted rounded-full" />
    );
  }

  if (isLoading) {
    return (
      <div className="h-9 w-9 animate-pulse bg-muted rounded-full" />
    );
  }

  return isAuthenticated ? <UserMenu /> : <LoginButton />;
}