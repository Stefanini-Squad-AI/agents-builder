"use client"

import { useState } from 'react';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { useLoginWithRedirect } from '@/lib/auth/hooks';
import { validateEmail } from '@/lib/auth/utils';
import { LoginRequest } from '@/lib/auth/types';

interface LoginFormProps {
  onSuccess?: () => void;
  className?: string;
}

export function LoginForm({ onSuccess, className }: LoginFormProps) {
  const [formData, setFormData] = useState<LoginRequest>({
    email: '',
    password: '',
    remember_me: false,
  });
  
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<keyof LoginRequest, string>>>({});
  
  const loginMutation = useLoginWithRedirect();

  const validateForm = (): boolean => {
    const newErrors: Partial<Record<keyof LoginRequest, string>> = {};

    // Email validation
    if (!formData.email) {
      newErrors.email = 'Email is required';
    } else if (!validateEmail(formData.email)) {
      newErrors.email = 'Please enter a valid email address';
    }

    // Password validation
    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    try {
      await loginMutation.mutateAsync(formData);
      onSuccess?.();
    } catch (error: any) {
      // Handle auth errors
      if (error.code === 'INVALID_CREDENTIALS') {
        setErrors({ email: 'Invalid email or password' });
      } else if (error.code === 'NETWORK_ERROR') {
        setErrors({ email: 'Network error. Please check your connection.' });
      } else {
        setErrors({ email: error.message || 'Login failed. Please try again.' });
      }
    }
  };

  const handleInputChange = (field: keyof LoginRequest, value: string | boolean) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
  };

  return (
    <div className={className}>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            placeholder="Enter your email"
            value={formData.email}
            onChange={(e) => handleInputChange('email', e.target.value)}
            className={errors.email ? 'border-destructive' : ''}
            disabled={loginMutation.isPending}
            autoComplete="email"
            autoFocus
          />
          {errors.email && (
            <p className="text-sm text-destructive">{errors.email}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? 'text' : 'password'}
              placeholder="Enter your password"
              value={formData.password}
              onChange={(e) => handleInputChange('password', e.target.value)}
              className={errors.password ? 'border-destructive pr-10' : 'pr-10'}
              disabled={loginMutation.isPending}
              autoComplete="current-password"
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
              onClick={() => setShowPassword(!showPassword)}
              disabled={loginMutation.isPending}
            >
              {showPassword ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </Button>
          </div>
          {errors.password && (
            <p className="text-sm text-destructive">{errors.password}</p>
          )}
        </div>

        <div className="flex items-center space-x-2">
          <Checkbox
            id="remember"
            checked={formData.remember_me}
            onCheckedChange={(checked) => 
              handleInputChange('remember_me', checked === true)
            }
            disabled={loginMutation.isPending}
          />
          <Label 
            htmlFor="remember" 
            className="text-sm font-normal cursor-pointer"
          >
            Remember me for 30 days
          </Label>
        </div>

        <Button 
          type="submit" 
          className="w-full" 
          disabled={loginMutation.isPending}
        >
          {loginMutation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Signing in...
            </>
          ) : (
            'Sign in'
          )}
        </Button>

        {loginMutation.error && (
          <div className="text-sm text-destructive text-center">
            Login failed. Please try again.
          </div>
        )}
      </form>

      <div className="mt-6 text-center text-sm">
        <a 
          href="/forgot-password" 
          className="text-primary hover:underline"
        >
          Forgot your password?
        </a>
      </div>

      <div className="mt-4 text-center text-sm text-muted-foreground">
        Don&apos;t have an account?{' '}
        <a 
          href="/register" 
          className="text-primary hover:underline"
        >
          Sign up
        </a>
      </div>
    </div>
  );
}