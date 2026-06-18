'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, Circle, Loader2, Star } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { QaAnswerView } from '@/lib/api/types';

interface QuestionCardProps {
  question: QaAnswerView;
  onAnswerChange: (questionKey: string, answerMd: string) => void;
  isLoading?: boolean;
  isSaving?: boolean;
  minLength?: number;
  debounceMs?: number;
}

/**
 * Individual question card component for the Q&A wizard.
 * Displays a question with a textarea for the answer, auto-saves on debounce.
 */
export function QuestionCard({
  question,
  onAnswerChange,
  isLoading = false,
  isSaving = false,
  minLength = 10,
  debounceMs = 1000,
}: QuestionCardProps) {
  const [localAnswer, setLocalAnswer] = useState(question.answer_md ?? '');
  const [isDirty, setIsDirty] = useState(false);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastSavedRef = useRef(question.answer_md ?? '');

  // Sync local state when external answer changes (e.g., from server refresh)
  useEffect(() => {
    if (!isDirty && question.answer_md !== lastSavedRef.current) {
      setLocalAnswer(question.answer_md ?? '');
      lastSavedRef.current = question.answer_md ?? '';
    }
  }, [question.answer_md, isDirty]);

  // Debounced save handler
  const handleChange = useCallback((value: string) => {
    setLocalAnswer(value);
    setIsDirty(true);

    // Clear existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Set new timer for auto-save
    debounceTimerRef.current = setTimeout(() => {
      if (value !== lastSavedRef.current) {
        onAnswerChange(question.question_key, value);
        lastSavedRef.current = value;
        setIsDirty(false);
      }
    }, debounceMs);
  }, [question.question_key, onAnswerChange, debounceMs]);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  // Calculate validation state
  const trimmedAnswer = localAnswer.trim();
  const isValid = trimmedAnswer.length >= minLength;
  const isAnswered = trimmedAnswer.length > 0;
  const showValidationWarning = question.required && isAnswered && !isValid;

  return (
    <Card
      className={cn(
        'transition-all duration-200',
        question.required && !isValid && 'border-amber-200 dark:border-amber-800',
        isValid && 'border-green-200 dark:border-green-800'
      )}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <CardTitle className="text-base font-medium leading-snug flex items-start gap-2">
            {/* Status icon */}
            {isLoading || isSaving ? (
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground shrink-0 mt-0.5" />
            ) : isValid ? (
              <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 shrink-0 mt-0.5" />
            ) : (
              <Circle className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
            )}
            
            <span>
              {question.prompt}
              {question.required && (
                <span className="text-red-500 ml-0.5" aria-label="Required">*</span>
              )}
            </span>
          </CardTitle>

          {/* Badges */}
          <div className="flex items-center gap-2 shrink-0">
            {question.required && (
              <Badge variant="secondary" className="gap-1 text-xs">
                <Star className="h-3 w-3" />
                Required
              </Badge>
            )}
            {isDirty && !isSaving && (
              <Badge variant="outline" className="text-xs text-muted-foreground">
                Unsaved
              </Badge>
            )}
            {isSaving && (
              <Badge variant="outline" className="text-xs text-blue-600 dark:text-blue-400">
                Saving...
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        <div className="space-y-2">
          <Textarea
            value={localAnswer}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={question.placeholder || 'Enter your answer...'}
            className={cn(
              'min-h-[120px] resize-y transition-colors',
              showValidationWarning && 'border-amber-400 focus-visible:ring-amber-400'
            )}
            disabled={isLoading}
          />
          
          {/* Character count and validation message */}
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {trimmedAnswer.length} characters
              {question.required && !isValid && (
                <span className="text-amber-600 dark:text-amber-400 ml-2">
                  (minimum {minLength} required)
                </span>
              )}
            </span>
            {question.updated_at && (
              <span>
                Last updated: {new Date(question.updated_at).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default QuestionCard;
