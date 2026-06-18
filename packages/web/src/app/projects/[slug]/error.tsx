'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertTriangle, Home, RefreshCw, FolderOpen } from 'lucide-react';

export default function ProjectError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const router = useRouter();

  useEffect(() => {
    console.error('Project error:', error);
  }, [error]);

  const isNotFound = error.message?.toLowerCase().includes('not found');

  return (
    <div className="container mx-auto py-8">
      <Card className="max-w-md mx-auto">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
            <AlertTriangle className="h-8 w-8 text-destructive" />
          </div>
          <CardTitle className="text-2xl">
            {isNotFound ? 'Project Not Found' : 'Error Loading Project'}
          </CardTitle>
          <CardDescription>
            {isNotFound
              ? "The project you're looking for doesn't exist or you don't have access."
              : 'There was a problem loading this project. Please try again.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error.message && !isNotFound && (
            <div className="rounded-lg bg-muted p-3 text-sm text-muted-foreground">
              <code>{error.message}</code>
            </div>
          )}
          <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
            {!isNotFound && (
              <Button onClick={reset} variant="default">
                <RefreshCw className="mr-2 h-4 w-4" />
                Try Again
              </Button>
            )}
            <Button variant="outline" asChild>
              <a href="/projects">
                <FolderOpen className="mr-2 h-4 w-4" />
                View All Projects
              </a>
            </Button>
            <Button variant="ghost" asChild>
              <a href="/dashboard">
                <Home className="mr-2 h-4 w-4" />
                Dashboard
              </a>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
