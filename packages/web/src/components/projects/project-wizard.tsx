'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  ChevronLeft, 
  ChevronRight, 
  Check, 
  Circle,
  FileText,
  MessageSquare,
  Wrench,
  FolderUp,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWizardStore, WIZARD_STEPS, type WizardStep } from '@/lib/store/wizard-store';
import { QaWizard } from '@/components/qa';
import { TechPanorama } from '@/components/tech';
import { ArtifactUpload } from '@/components/artifacts';
import { useQaStats } from '@/lib/api/queries/use-qa';
import { useTechStats } from '@/lib/api/queries/use-tech';

interface ProjectWizardProps {
  projectSlug?: string;
  projectId?: string;
  initialStep?: WizardStep;
}

const StepIcons: Record<WizardStep, React.ElementType> = {
  identity: FileText,
  qa: MessageSquare,
  tech: Wrench,
  artifacts: FolderUp,
};

/**
 * Multi-step project creation wizard.
 * Step 1: Identity - Project name and basic info
 * Step 2: Q&A Discovery - Answer 7 questions (3 required)
 * Step 3: Tech Stack - Select technologies
 * Step 4: Artifacts - Upload documents
 */
export function ProjectWizard({ 
  projectSlug, 
  projectId,
  initialStep = 'identity',
}: ProjectWizardProps) {
  const router = useRouter();
  
  const {
    currentStep,
    currentStepIndex,
    stepStatuses,
    setProject,
    goToStep,
    nextStep,
    prevStep,
    setStepStatus,
    getProgress,
    reset,
  } = useWizardStore();

  // Sync project with store on mount
  useEffect(() => {
    if (projectSlug && projectId) {
      setProject(projectSlug, projectId);
      // If project exists, identity step is complete
      setStepStatus('identity', { completed: true, canProceed: true });
      
      // Start at initial step
      if (initialStep) {
        goToStep(initialStep);
      }
    }
  }, [projectSlug, projectId, initialStep, setProject, setStepStatus, goToStep]);

  // Fetch Q&A stats to determine if Q&A step is complete
  const { data: qaStats } = useQaStats(projectSlug ?? '', !!projectSlug);

  // Fetch Tech stats to determine if tech step is complete
  const { data: techStats } = useTechStats(projectSlug ?? '', !!projectSlug);

  // Update Q&A step status based on stats
  useEffect(() => {
    if (qaStats) {
      const allRequiredAnswered = qaStats.required_answered === qaStats.required_total;
      setStepStatus('qa', {
        completed: allRequiredAnswered,
        canProceed: allRequiredAnswered,
        validationErrors: allRequiredAnswered 
          ? [] 
          : [`Answer ${qaStats.required_total - qaStats.required_answered} more required questions`],
      });
    }
  }, [qaStats, setStepStatus]);

  // Update Tech step status based on stats
  useEffect(() => {
    if (techStats) {
      // Tech step can always proceed (optional) but is "complete" if at least one dimension answered
      const hasAnswered = techStats.covered_dimensions > 0;
      setStepStatus('tech', {
        completed: hasAnswered,
        canProceed: true, // Always allow proceeding
        validationErrors: [],
      });
    }
  }, [techStats, setStepStatus]);

  const progress = getProgress();

  // Handle step completion callbacks
  const handleQaComplete = () => {
    nextStep();
  };

  const handleTechComplete = () => {
    nextStep();
  };

  const handleFinish = () => {
    // Navigate to project page when done
    if (projectSlug) {
      router.push(`/projects/${projectSlug}` as Parameters<typeof router.push>[0]);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-6 space-y-6">
      {/* Header with progress */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Project Setup</h1>
            <p className="text-muted-foreground">
              Configure your project in a few simple steps
            </p>
          </div>
          <div className="text-right">
            <div className="text-sm font-medium">
              Step {currentStepIndex + 1} of {WIZARD_STEPS.length}
            </div>
            <div className="text-xs text-muted-foreground">
              {progress.percentage}% complete
            </div>
          </div>
        </div>

        {/* Step indicators */}
        <div className="flex items-center gap-2">
          {WIZARD_STEPS.map((step, index) => {
            const Icon = StepIcons[step.key];
            const status = stepStatuses[step.key];
            const isActive = currentStepIndex === index;
            const isPast = currentStepIndex > index;
            const canClick = index < currentStepIndex || stepStatuses[WIZARD_STEPS[index - 1]?.key]?.canProceed !== false;

            return (
              <div key={step.key} className="flex items-center flex-1">
                <button
                  onClick={() => canClick && goToStep(step.key)}
                  disabled={!canClick}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 rounded-lg transition-all w-full',
                    'hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed',
                    isActive && 'bg-primary text-primary-foreground',
                    !isActive && status.completed && 'bg-green-100 dark:bg-green-900',
                    !isActive && !status.completed && 'bg-muted'
                  )}
                >
                  <div className={cn(
                    'flex items-center justify-center w-8 h-8 rounded-full shrink-0',
                    isActive && 'bg-primary-foreground text-primary',
                    !isActive && status.completed && 'bg-green-500 text-white',
                    !isActive && !status.completed && 'bg-background border-2'
                  )}>
                    {status.completed ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <Icon className="h-4 w-4" />
                    )}
                  </div>
                  <div className="text-left min-w-0 hidden sm:block">
                    <div className="text-sm font-medium truncate">{step.label}</div>
                    <div className="text-xs opacity-70 truncate">{step.description}</div>
                  </div>
                </button>
                {index < WIZARD_STEPS.length - 1 && (
                  <div className={cn(
                    'w-8 h-0.5 mx-2 shrink-0',
                    isPast ? 'bg-green-500' : 'bg-border'
                  )} />
                )}
              </div>
            );
          })}
        </div>

        <Progress value={progress.percentage} className="h-1" />
      </div>

      {/* Step content */}
      <Card>
        <CardContent className="pt-6">
          {currentStep === 'identity' && (
            <IdentityStep 
              onComplete={() => nextStep()} 
              projectSlug={projectSlug}
            />
          )}

          {currentStep === 'qa' && projectSlug && (
            <QaWizard 
              projectSlug={projectSlug} 
              onComplete={handleQaComplete}
            />
          )}

          {currentStep === 'tech' && projectSlug && (
            <TechPanorama 
              projectSlug={projectSlug} 
              onContinue={handleTechComplete}
            />
          )}

          {currentStep === 'artifacts' && projectSlug && (
            <ArtifactsStep 
              projectSlug={projectSlug}
              onComplete={handleFinish} 
            />
          )}
        </CardContent>
      </Card>

      {/* Navigation buttons */}
      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={prevStep}
          disabled={currentStepIndex === 0}
        >
          <ChevronLeft className="mr-2 h-4 w-4" />
          Previous
        </Button>

        <div className="flex gap-2">
          {currentStepIndex < WIZARD_STEPS.length - 1 ? (
            <Button
              onClick={nextStep}
              disabled={!stepStatuses[currentStep].canProceed}
            >
              Next
              <ChevronRight className="ml-2 h-4 w-4" />
            </Button>
          ) : (
            <Button onClick={handleFinish}>
              Finish Setup
              <Check className="ml-2 h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

// Placeholder step components - to be fully implemented
interface StepProps {
  onComplete: () => void;
  projectSlug?: string;
}

function IdentityStep({ onComplete, projectSlug }: StepProps) {
  if (projectSlug) {
    return (
      <div className="text-center py-8">
        <Check className="h-16 w-16 mx-auto text-green-500 mb-4" />
        <h3 className="text-lg font-semibold">Project Created</h3>
        <p className="text-muted-foreground mb-4">
          Your project has been created. Continue to set up discovery Q&A.
        </p>
        <Button onClick={onComplete}>
          Continue to Q&A
          <ChevronRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Create New Project</h3>
      <p className="text-muted-foreground">
        Enter basic information about your project.
      </p>
      {/* Full identity form to be implemented */}
      <div className="py-8 text-center text-muted-foreground">
        Identity form placeholder - use existing project creation flow
      </div>
    </div>
  );
}

function ArtifactsStep({ projectSlug, onComplete }: StepProps) {
  if (!projectSlug) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        Project slug is required for artifact upload.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <ArtifactUpload projectSlug={projectSlug} showTitle={false} />
      
      <div className="flex justify-end pt-4 border-t">
        <Button onClick={onComplete}>
          Complete Setup
          <Check className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

export default ProjectWizard;
