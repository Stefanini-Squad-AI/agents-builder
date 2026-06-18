'use client';

import { useCallback, useState } from 'react';
import { useQaAnswers, useSetQaAnswer, useQaStats } from '@/lib/api/queries/use-qa';
import { QaAnswerView } from '@/lib/api/types';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  ChevronLeft, 
  ChevronRight, 
  Loader2, 
  CheckCircle2,
  AlertCircle,
  Save
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface QaStepProps {
  projectSlug: string;
  onNext: () => void;
  onPrev: () => void;
}

export function QaStep({ projectSlug, onNext, onPrev }: QaStepProps) {
  const { data: answers, isLoading } = useQaAnswers(projectSlug);
  const { data: stats } = useQaStats(projectSlug);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const requiredAnswers = answers?.filter(a => a.required) || [];
  const optionalAnswers = answers?.filter(a => !a.required) || [];
  const allRequiredAnswered = stats?.required_percentage === 100;

  return (
    <div className="space-y-6">
      {/* Description */}
      <div className="space-y-2">
        <p className="text-muted-foreground">
          Answer these discovery questions to help the AI understand your project context.
          The first three questions are required before you can proceed.
        </p>
        
        {/* Progress */}
        {stats && (
          <div className="flex items-center gap-4">
            <Progress value={stats.completion_percentage} className="flex-1" />
            <span className="text-sm text-muted-foreground">
              {stats.answered_questions}/{stats.total_questions} answered
            </span>
          </div>
        )}
      </div>

      {/* Required Questions */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          Required Questions
          {allRequiredAnswered && (
            <CheckCircle2 className="h-4 w-4 text-green-500" />
          )}
        </h3>
        {requiredAnswers.map((answer) => (
          <QuestionCard 
            key={answer.question_key} 
            answer={answer} 
            projectSlug={projectSlug}
          />
        ))}
      </div>

      {/* Optional Questions */}
      {optionalAnswers.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-muted-foreground">
            Optional Questions
          </h3>
          {optionalAnswers.map((answer) => (
            <QuestionCard 
              key={answer.question_key} 
              answer={answer} 
              projectSlug={projectSlug}
            />
          ))}
        </div>
      )}

      {/* Validation Warning */}
      {!allRequiredAnswered && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Please answer all required questions before continuing.
          </AlertDescription>
        </Alert>
      )}

      {/* Navigation */}
      <div className="flex justify-between pt-4 border-t">
        <Button variant="outline" onClick={onPrev}>
          <ChevronLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        <Button onClick={onNext} disabled={!allRequiredAnswered}>
          Continue
          <ChevronRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function QuestionCard({ answer, projectSlug }: { answer: QaAnswerView; projectSlug: string }) {
  const [value, setValue] = useState(answer.answer_md || '');
  const [isDirty, setIsDirty] = useState(false);
  
  const setQaAnswer = useSetQaAnswer(projectSlug, answer.question_key);

  const handleSave = useCallback(async () => {
    try {
      await setQaAnswer.mutateAsync({ answer_md: value });
      setIsDirty(false);
    } catch (error) {
      console.error('Failed to save answer:', error);
    }
  }, [setQaAnswer, value]);

  const handleChange = useCallback((newValue: string) => {
    setValue(newValue);
    setIsDirty(newValue !== (answer.answer_md || ''));
  }, [answer.answer_md]);

  const handleBlur = useCallback(() => {
    if (isDirty && value.trim()) {
      handleSave();
    }
  }, [isDirty, value, handleSave]);

  return (
    <div className={cn(
      'border rounded-lg p-4 space-y-3',
      answer.required && !answer.is_answered && 'border-yellow-500/50 bg-yellow-500/5'
    )}>
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-medium">{answer.prompt}</span>
            {answer.required && (
              <Badge variant="secondary" className="text-xs">Required</Badge>
            )}
          </div>
        </div>
        {answer.is_answered && (
          <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
        )}
      </div>

      {/* Textarea */}
      <Textarea
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        onBlur={handleBlur}
        placeholder={answer.placeholder}
        rows={4}
        className="resize-none"
      />

      {/* Footer */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {answer.updated_at && `Last updated: ${new Date(answer.updated_at).toLocaleDateString()}`}
        </span>
        {isDirty && (
          <Button 
            size="sm" 
            onClick={handleSave}
            disabled={setQaAnswer.isPending}
          >
            {setQaAnswer.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <Save className="h-4 w-4 mr-1" />
                Save
              </>
            )}
          </Button>
        )}
      </div>
    </div>
  );
}
