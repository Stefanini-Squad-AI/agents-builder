'use client';

import { useMemo, useCallback } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { 
  AlertCircle, 
  CheckCircle2, 
  Info,
  ArrowRight,
  Loader2,
} from 'lucide-react';
import { QuestionCard } from './question-card';
import { useQaAnswers, useQaStats, useSetQaAnswer } from '@/lib/api/queries/use-qa';
import type { QaAnswerView } from '@/lib/api/types';

interface QaWizardProps {
  projectSlug: string;
  onComplete?: () => void;
  minAnswerLength?: number;
}

/**
 * Q&A Wizard component for project discovery.
 * Shows all 7 questions with 3 required, auto-saves on debounce.
 */
export function QaWizard({
  projectSlug,
  onComplete,
  minAnswerLength = 10,
}: QaWizardProps) {
  // Fetch all Q&A data
  const { 
    data: qaAnswers, 
    isLoading: isLoadingAnswers,
    error: answersError,
  } = useQaAnswers(projectSlug);

  const {
    data: qaStats,
    isLoading: isLoadingStats,
  } = useQaStats(projectSlug);

  // Sort questions by order
  const sortedQuestions = useMemo(() => {
    if (!qaAnswers) return [];
    return [...qaAnswers].sort((a, b) => a.order - b.order);
  }, [qaAnswers]);

  // Calculate readiness
  const { canProceed, requiredAnswered, requiredTotal, missingRequired } = useMemo(() => {
    if (!sortedQuestions.length) {
      return { canProceed: false, requiredAnswered: 0, requiredTotal: 0, missingRequired: [] };
    }

    const required = sortedQuestions.filter(q => q.required);
    const answeredRequired = required.filter(
      q => q.answer_md && q.answer_md.trim().length >= minAnswerLength
    );
    const missing = required.filter(
      q => !q.answer_md || q.answer_md.trim().length < minAnswerLength
    );

    return {
      canProceed: answeredRequired.length === required.length,
      requiredAnswered: answeredRequired.length,
      requiredTotal: required.length,
      missingRequired: missing.map(q => q.prompt),
    };
  }, [sortedQuestions, minAnswerLength]);

  // Loading state
  if (isLoadingAnswers) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-full" />
        <div className="space-y-4 mt-6">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-48 w-full" />
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (answersError) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Error loading questions</AlertTitle>
        <AlertDescription>
          {answersError instanceof Error 
            ? answersError.message 
            : 'Failed to load Q&A questions. Please try again.'}
        </AlertDescription>
      </Alert>
    );
  }

  // Calculate progress percentage
  const progressPercentage = qaStats 
    ? qaStats.completion_percentage 
    : sortedQuestions.length > 0
      ? (sortedQuestions.filter(q => q.is_answered).length / sortedQuestions.length) * 100
      : 0;

  return (
    <div className="space-y-6">
      {/* Header with progress */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Project Discovery</h2>
            <p className="text-sm text-muted-foreground">
              Answer the following questions to help us understand your project.
              Questions marked with <span className="text-red-500">*</span> are required.
            </p>
          </div>
          {isLoadingStats ? (
            <Skeleton className="h-9 w-24" />
          ) : (
            <div className="text-right">
              <div className="text-2xl font-bold">
                {qaStats?.answered_questions ?? 0}/{qaStats?.total_questions ?? sortedQuestions.length}
              </div>
              <div className="text-xs text-muted-foreground">Questions answered</div>
            </div>
          )}
        </div>

        {/* Progress bar */}
        <div className="space-y-1">
          <Progress value={progressPercentage} className="h-2" />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>
              Required: {requiredAnswered}/{requiredTotal} answered
            </span>
            <span>{Math.round(progressPercentage)}% complete</span>
          </div>
        </div>
      </div>

      {/* Info alert about required questions */}
      <Alert>
        <Info className="h-4 w-4" />
        <AlertTitle>Required Questions</AlertTitle>
        <AlertDescription>
          You must answer at least the {requiredTotal} required questions before proceeding.
          Each required answer must be at least {minAnswerLength} characters.
        </AlertDescription>
      </Alert>

      {/* Question cards */}
      <div className="space-y-4">
        {sortedQuestions.map((question) => (
          <QuestionCardWrapper
            key={question.question_key}
            projectSlug={projectSlug}
            question={question}
            minLength={minAnswerLength}
          />
        ))}
      </div>

      {/* Completion status */}
      <div className="pt-4 border-t">
        {canProceed ? (
          <Alert className="bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800">
            <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
            <AlertTitle className="text-green-800 dark:text-green-200">Ready to proceed!</AlertTitle>
            <AlertDescription className="text-green-700 dark:text-green-300">
              All required questions have been answered. You can continue to the next step.
            </AlertDescription>
          </Alert>
        ) : (
          <Alert className="bg-amber-50 dark:bg-amber-950 border-amber-200 dark:border-amber-800">
            <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
            <AlertTitle className="text-amber-800 dark:text-amber-200">
              {requiredTotal - requiredAnswered} required {requiredTotal - requiredAnswered === 1 ? 'question' : 'questions'} remaining
            </AlertTitle>
            <AlertDescription className="text-amber-700 dark:text-amber-300">
              <ul className="list-disc list-inside mt-1">
                {missingRequired.slice(0, 3).map((prompt, i) => (
                  <li key={i} className="truncate">{prompt}</li>
                ))}
                {missingRequired.length > 3 && (
                  <li>...and {missingRequired.length - 3} more</li>
                )}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        {/* Action button */}
        {onComplete && (
          <div className="flex justify-end mt-4">
            <Button
              onClick={onComplete}
              disabled={!canProceed}
              size="lg"
            >
              Continue to Tech Stack
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Wrapper component for QuestionCard that handles the mutation.
 */
interface QuestionCardWrapperProps {
  projectSlug: string;
  question: QaAnswerView;
  minLength: number;
}

function QuestionCardWrapper({ projectSlug, question, minLength }: QuestionCardWrapperProps) {
  const { mutate, isPending } = useSetQaAnswer(projectSlug, question.question_key);

  const handleAnswerChange = useCallback((questionKey: string, answerMd: string) => {
    mutate({ answer_md: answerMd });
  }, [mutate]);

  return (
    <QuestionCard
      question={question}
      onAnswerChange={handleAnswerChange}
      isSaving={isPending}
      minLength={minLength}
    />
  );
}

export default QaWizard;
