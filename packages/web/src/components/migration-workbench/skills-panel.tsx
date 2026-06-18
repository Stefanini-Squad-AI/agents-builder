'use client';

import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Loader2,
  BookOpen,
  Lightbulb,
  ChevronRight,
  Folder,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useMigrationSkills, useMigrationSkill } from '@/lib/api/queries/use-migration-skills';
import type { SkillSummary } from '@/lib/api/types';
import ReactMarkdown from 'react-markdown';

export function SkillsPanel() {
  const { data: skills, isLoading, error } = useMigrationSkills();
  const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !skills) {
    return (
      <div className="text-center text-muted-foreground py-8">
        Failed to load skills
      </div>
    );
  }

  if (skills.length === 0) {
    return (
      <div className="text-center text-muted-foreground py-8">
        <Lightbulb className="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p>No pre-built skills available</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Lightbulb className="h-4 w-4" />
        <span>{skills.length} pre-built skills available</span>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {skills.map((skill) => (
          <SkillCard
            key={skill.id}
            skill={skill}
            onSelect={() => setSelectedSkillId(skill.id)}
          />
        ))}
      </div>

      <SkillDetailDialog
        skillId={selectedSkillId}
        open={!!selectedSkillId}
        onOpenChange={(open) => !open && setSelectedSkillId(null)}
      />
    </div>
  );
}

interface SkillCardProps {
  skill: SkillSummary;
  onSelect: () => void;
}

function SkillCard({ skill, onSelect }: SkillCardProps) {
  return (
    <Card 
      className="cursor-pointer hover:border-primary/50 transition-colors"
      onClick={onSelect}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <CardTitle className="text-base">{skill.name}</CardTitle>
          </div>
          {skill.has_resources && (
            <Badge variant="outline" className="text-xs gap-1">
              <Folder className="h-3 w-3" />
              Resources
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <CardDescription className="line-clamp-2 mb-3">
          {skill.description}
        </CardDescription>
        
        {skill.capabilities.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {skill.capabilities.slice(0, 3).map((cap, idx) => (
              <Badge key={idx} variant="secondary" className="text-xs">
                {cap}
              </Badge>
            ))}
            {skill.capabilities.length > 3 && (
              <Badge variant="outline" className="text-xs">
                +{skill.capabilities.length - 3} more
              </Badge>
            )}
          </div>
        )}

        <div className="flex justify-end mt-3">
          <Button variant="ghost" size="sm" className="gap-1 text-xs">
            View Details
            <ChevronRight className="h-3 w-3" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

interface SkillDetailDialogProps {
  skillId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function SkillDetailDialog({ skillId, open, onOpenChange }: SkillDetailDialogProps) {
  const { data: skill, isLoading } = useMigrationSkill(skillId || '');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] flex flex-col">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : skill ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <BookOpen className="h-5 w-5" />
                {skill.name}
              </DialogTitle>
              <DialogDescription>{skill.description}</DialogDescription>
            </DialogHeader>

            {skill.when_to_use && (
              <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm">
                <div className="font-medium text-blue-800 mb-1">When to Use</div>
                <div className="text-blue-700 whitespace-pre-wrap">
                  {skill.when_to_use}
                </div>
              </div>
            )}

            <ScrollArea className="flex-1 pr-4">
              <article className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown>{skill.content}</ReactMarkdown>
              </article>
            </ScrollArea>
          </>
        ) : (
          <div className="text-center text-muted-foreground py-8">
            Skill not found
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
