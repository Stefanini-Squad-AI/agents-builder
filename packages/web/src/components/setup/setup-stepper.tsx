'use client';

import { CheckCircle2, Circle } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface Step {
  id: number;
  name: string;
  description?: string;
  completed: boolean;
}

interface SetupStepperProps {
  steps: Step[];
  currentStep: number;
  onStepClick?: (step: number) => void;
}

export function SetupStepper({ steps, currentStep, onStepClick }: SetupStepperProps) {
  return (
    <nav aria-label="Progress">
      <ol className="flex items-center justify-between">
        {steps.map((step, index) => {
          const isActive = step.id === currentStep;
          const isPast = step.id < currentStep;
          const isClickable = onStepClick && (step.completed || step.id <= currentStep);

          return (
            <li key={step.id} className="relative flex-1">
              {/* Connector line */}
              {index < steps.length - 1 && (
                <div
                  className={cn(
                    'absolute top-5 left-1/2 w-full h-0.5',
                    isPast || step.completed ? 'bg-primary' : 'bg-muted'
                  )}
                  aria-hidden="true"
                />
              )}

              {/* Step circle and label */}
              <button
                type="button"
                className={cn(
                  'relative flex flex-col items-center group',
                  isClickable ? 'cursor-pointer' : 'cursor-default'
                )}
                onClick={() => isClickable && onStepClick?.(step.id)}
                disabled={!isClickable}
              >
                {/* Circle indicator */}
                <span
                  className={cn(
                    'relative z-10 flex h-10 w-10 items-center justify-center rounded-full border-2 bg-background transition-colors',
                    isActive && 'border-primary bg-primary text-primary-foreground',
                    !isActive && step.completed && 'border-primary bg-primary text-primary-foreground',
                    !isActive && !step.completed && 'border-muted-foreground/30'
                  )}
                >
                  {step.completed ? (
                    <CheckCircle2 className="h-5 w-5" />
                  ) : (
                    <span className={cn(
                      'text-sm font-medium',
                      isActive ? 'text-primary-foreground' : 'text-muted-foreground'
                    )}>
                      {step.id}
                    </span>
                  )}
                </span>

                {/* Label */}
                <span
                  className={cn(
                    'mt-2 text-sm font-medium transition-colors',
                    isActive ? 'text-primary' : 'text-muted-foreground',
                    isClickable && 'group-hover:text-primary'
                  )}
                >
                  {step.name}
                </span>

                {/* Description (hidden on mobile) */}
                {step.description && (
                  <span className="mt-0.5 text-xs text-muted-foreground hidden sm:block">
                    {step.description}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
