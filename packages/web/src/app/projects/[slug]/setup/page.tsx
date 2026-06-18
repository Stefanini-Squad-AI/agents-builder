'use client';

import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo } from 'react';
import { useProject } from '@/lib/api/queries/use-projects';
import { useProjectArtifacts } from '@/lib/api/queries/use-artifacts';
import { useQaStats, useProjectReadiness } from '@/lib/api/queries/use-qa';
import { useProjectTechChoices } from '@/lib/api/queries/use-tech';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowLeft, Loader2 } from 'lucide-react';

import { SetupStepper, Step } from '@/components/setup/setup-stepper';
import { ArtifactsStep } from '@/components/setup/artifacts-step';
import { QaStep } from '@/components/setup/qa-step';
import { TechStep } from '@/components/setup/tech-step';
import { ReviewStep } from '@/components/setup/review-step';

/**
 * Project Setup Wizard - guides users through discovery channels
 * Step 1: Artifacts upload
 * Step 2: Q&A wizard (7 questions, 3 required)
 * Step 3: Tech panorama (chip selection + AI suggestions)
 * Step 4: Review & continue
 */
export default function SetupPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectSlug = params.slug as string;

  // Get current step from URL, default to 1
  const currentStep = parseInt(searchParams.get('step') || '1', 10);

  // Fetch project data
  const { data: project, isLoading: isLoadingProject } = useProject(projectSlug);
  
  // Fetch completion data for each step - refetch on mount to get fresh data
  const { data: artifacts, refetch: refetchArtifacts } = useProjectArtifacts(projectSlug);
  const { data: qaStats, refetch: refetchQaStats } = useQaStats(projectSlug);
  const { data: techChoices, refetch: refetchTechChoices } = useProjectTechChoices(projectSlug);
  const { data: readiness, refetch: refetchReadiness } = useProjectReadiness(projectSlug);

  // Refetch data when step changes to ensure fresh data
  useEffect(() => {
    refetchArtifacts();
    refetchQaStats();
    refetchTechChoices();
    refetchReadiness();
  }, [currentStep, refetchArtifacts, refetchQaStats, refetchTechChoices, refetchReadiness]);

  // Calculate step completion
  const steps: Step[] = useMemo(() => [
    {
      id: 1,
      name: 'Artifacts',
      description: 'Upload documents and code',
      completed: (artifacts?.length || 0) > 0,
    },
    {
      id: 2,
      name: 'Q&A',
      description: 'Answer discovery questions',
      completed: (qaStats?.required_percentage || 0) === 100,
    },
    {
      id: 3,
      name: 'Tech Stack',
      description: 'Select technologies',
      completed: (techChoices?.length || 0) > 0,
    },
    {
      id: 4,
      name: 'Review',
      description: 'Verify and continue',
      completed: false,
    },
  ], [artifacts, qaStats, techChoices]);

  // Navigation handlers
  const goToStep = useCallback((step: number) => {
    router.push(`/projects/${projectSlug}/setup?step=${step}`);
  }, [router, projectSlug]);

  const goNext = useCallback(() => {
    if (currentStep < 4) {
      goToStep(currentStep + 1);
    }
  }, [currentStep, goToStep]);

  const goPrev = useCallback(() => {
    if (currentStep > 1) {
      goToStep(currentStep - 1);
    }
  }, [currentStep, goToStep]);

  const goToProject = useCallback(() => {
    router.push(`/projects/${projectSlug}`);
  }, [router, projectSlug]);

  if (isLoadingProject) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <div className="text-center space-y-4">
          <h2 className="text-xl font-semibold">Project not found</h2>
          <Button variant="outline" onClick={() => router.push('/projects')}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Projects
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="container max-w-5xl py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={goToProject}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Project
        </Button>
        <div className="h-6 w-px bg-border" />
        <div>
          <h1 className="text-2xl font-bold">Project Setup</h1>
          <p className="text-muted-foreground text-sm">{project.name}</p>
        </div>
      </div>

      {/* Stepper */}
      <SetupStepper 
        steps={steps} 
        currentStep={currentStep} 
        onStepClick={goToStep}
      />

      {/* Step Content */}
      <Card>
        <CardHeader>
          <CardTitle>{steps[currentStep - 1]?.name}</CardTitle>
        </CardHeader>
        <CardContent>
          {currentStep === 1 && (
            <ArtifactsStep 
              projectSlug={projectSlug}
              onNext={goNext}
            />
          )}
          {currentStep === 2 && (
            <QaStep 
              projectSlug={projectSlug}
              onNext={goNext}
              onPrev={goPrev}
            />
          )}
          {currentStep === 3 && (
            <TechStep 
              projectSlug={projectSlug}
              onNext={goNext}
              onPrev={goPrev}
            />
          )}
          {currentStep === 4 && (
            <ReviewStep 
              projectSlug={projectSlug}
              readiness={readiness}
              artifactCount={artifacts?.length || 0}
              qaStats={qaStats}
              techChoiceCount={techChoices?.length || 0}
              onPrev={goPrev}
              onFinish={() => router.push(`/projects/${projectSlug}/skills`)}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
