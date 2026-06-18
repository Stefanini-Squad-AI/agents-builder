import { Metadata } from 'next';
import { LoginForm } from '@/components/auth/login-form';

export const metadata: Metadata = {
  title: 'Sign In - Agents Workshop',
  description: 'Sign in to your Agents Workshop account',
};

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight">
            Welcome back
          </h1>
          <p className="mt-2 text-muted-foreground">
            Sign in to your account to continue
          </p>
        </div>
        
        <div className="bg-card rounded-lg border p-8 shadow-sm">
          <LoginForm />
        </div>

        {/* Development helper */}
        {process.env.NODE_ENV === 'development' && (
          <div className="text-center">
            <details className="text-sm">
              <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                Development Info
              </summary>
              <div className="mt-2 p-4 bg-muted rounded-md text-left">
                <p className="font-medium mb-2">Test Credentials:</p>
                <p>Email: admin@example.com</p>
                <p>Password: password123</p>
                <p className="text-xs text-muted-foreground mt-2">
                  Note: This will only work if the backend is running
                </p>
              </div>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}