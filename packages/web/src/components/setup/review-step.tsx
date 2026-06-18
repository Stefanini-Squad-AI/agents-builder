'use client';

import { QaStatsView, QaReadinessView } from '@/lib/api/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { 
  ChevronLeft, 
  CheckCircle2, 
  AlertCircle,
  FileText,
  MessageSquare,
  Layers,
  Sparkles,
  ArrowRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface ReviewStepProps {
  projectSlug: string;
  readiness?: QaReadinessView;
  artifactCount: number;
  qaStats?: QaStatsView;
  techChoiceCount: number;
  onPrev: () => void;
  onFinish: () => void;
}

export function ReviewStep({ 
  projectSlug,
  readiness, 
  artifactCount, 
  qaStats, 
  techChoiceCount,
  onPrev,
  onFinish,
}: ReviewStepProps) {
  const isReady = readiness?.ready ?? false;
  const readinessLevel = readiness?.readiness ?? 'blocked';

  const summaryItems = [
    {
      icon: FileText,
      label: 'Artifacts',
      value: artifactCount,
      description: 'context documents uploaded',
      completed: artifactCount > 0,
    },
    {
      icon: MessageSquare,
      label: 'Q&A',
      value: `${qaStats?.answered_questions || 0}/${qaStats?.total_questions || 7}`,
      description: 'discovery questions answered',
      completed: (qaStats?.required_percentage || 0) === 100,
      required: true,
    },
    {
      icon: Layers,
      label: 'Tech Stack',
      value: techChoiceCount,
      description: 'technologies selected',
      completed: techChoiceCount > 0,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Description */}
      <p className="text-muted-foreground">
        Review your project setup before continuing to generate skills and backlog.
      </p>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {summaryItems.map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.label} className={cn(
              'relative',
              item.required && !item.completed && 'border-yellow-500'
            )}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Icon className="h-4 w-4" />
                  {item.label}
                  {item.required && (
                    <Badge variant="secondary" className="text-xs">Required</Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-2xl font-bold">{item.value}</div>
                    <p className="text-xs text-muted-foreground">{item.description}</p>
                  </div>
                  {item.completed && (
                    <CheckCircle2 className="h-6 w-6 text-green-500" />
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Readiness Status */}
      {readiness && (
        <Alert variant={isReady ? 'default' : 'destructive'}>
          {isReady ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <AlertCircle className="h-4 w-4" />
          )}
          <AlertTitle>
            {isReady ? 'Ready to Continue' : 'Setup Incomplete'}
          </AlertTitle>
          <AlertDescription>
            {readiness.message}
            {readiness.missing_required.length > 0 && (
              <ul className="mt-2 list-disc list-inside">
                {readiness.missing_required.map((key) => (
                  <li key={key} className="text-sm">
                    Missing: {key.replace(/_/g, ' ')}
                  </li>
                ))}
              </ul>
            )}
          </AlertDescription>
        </Alert>
      )}

      {/* Recommended Next Steps */}
      {readiness?.recommended_next_steps && readiness.recommended_next_steps.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold">Recommended Next Steps</h3>
          <ul className="space-y-1">
            {readiness.recommended_next_steps.map((step, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-muted-foreground">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-muted text-xs">
                  {i + 1}
                </span>
                {step}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* What's Next */}
      <Card className="bg-primary/5 border-primary/20">
        <CardContent className="pt-6">
          <div className="flex items-start gap-4">
            <div className="rounded-full bg-primary/10 p-3">
              <Sparkles className="h-6 w-6 text-primary" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold">What happens next?</h3>
              <p className="text-sm text-muted-foreground mt-1">
                After completing setup, you&apos;ll be able to:
              </p>
              <ol className="mt-2 space-y-1 text-sm">
                <li className="flex items-center gap-2">
                  <span className="font-medium">1.</span>
                  Generate a skill set based on your project context
                </li>
                <li className="flex items-center gap-2">
                  <span className="font-medium">2.</span>
                  Create a phased backlog of implementation cards
                </li>
                <li className="flex items-center gap-2">
                  <span className="font-medium">3.</span>
                  Visualize dependencies in the DAG view
                </li>
                <li className="flex items-center gap-2">
                  <span className="font-medium">4.</span>
                  Export the .agents/ folder for AI coding agents
                </li>
              </ol>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex justify-between pt-4 border-t">
        <Button variant="outline" onClick={onPrev}>
          <ChevronLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        <Button onClick={onFinish} disabled={!isReady}>
          <Sparkles className="mr-2 h-4 w-4" />
          Continue to Skills
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
