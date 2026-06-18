'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { AlertTriangle, ArrowLeft, RefreshCw } from 'lucide-react';

export default function McpIntegrationsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const router = useRouter();

  useEffect(() => {
    console.error('MCP Integrations page error:', error);
  }, [error]);

  return (
    <div className="container mx-auto py-8">
      <Card className="mx-auto max-w-xl">
        <CardHeader className="flex-row items-start gap-3">
          <AlertTriangle className="mt-1 h-5 w-5 text-destructive" />
          <div>
            <CardTitle>Failed to load MCP Integrations</CardTitle>
            <CardDescription className="mt-1">
              {error.message || 'An unexpected error occurred.'}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button onClick={() => reset()} size="sm">
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry
          </Button>
          <Button variant="outline" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to project
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
