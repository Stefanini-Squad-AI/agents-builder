'use client';

import { useParams, useRouter } from 'next/navigation';
import { useState, useCallback, useEffect, useRef } from 'react';
import {
  useCard,
  useCards,
  useUpdateCard,
  useUpdateCardSection,
  useRegenerateCardSection,
  useDraftCardContent,
  useUpdateCardDependencies,
} from '@/lib/api/queries';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { CodeEditor } from '@/components/ui/code-editor';
import { CardInputsEditor } from '@/components/cards/card-inputs-editor';
import { CardDependenciesEditor } from '@/components/cards/card-dependencies-editor';
import { Priority, CardStatus, CardView } from '@/lib/api/types';
import { ArrowLeft, Sparkles, Loader2, FileText, CheckSquare, Target, ListChecks, AlertCircle, Link2, FileInput } from 'lucide-react';

const PRIORITY_OPTIONS: { value: Priority; label: string }[] = [
  { value: Priority.LOW, label: 'Low' },
  { value: Priority.MEDIUM, label: 'Medium' },
  { value: Priority.HIGH, label: 'High' },
];

const STATUS_OPTIONS: { value: CardStatus; label: string }[] = [
  { value: CardStatus.DRAFT, label: 'Draft' },
  { value: CardStatus.READY, label: 'Ready' },
  { value: CardStatus.IN_PROGRESS, label: 'In Progress' },
  { value: CardStatus.DONE, label: 'Done' },
];

const SECTIONS = [
  { key: 'context', label: 'Context', icon: FileText, description: 'Background and setup for this card' },
  { key: 'task', label: 'Task', icon: Target, description: 'What needs to be done' },
  { key: 'outputs', label: 'Outputs', icon: CheckSquare, description: 'Expected deliverables' },
  { key: 'acceptance_criteria', label: 'Acceptance Criteria', icon: ListChecks, description: 'Definition of done' },
] as const;

const DEBOUNCE_DELAY = 1000;

export default function CardEditorPage() {
  const params = useParams();
  const router = useRouter();
  const projectSlug = params.slug as string;
  const cardId = params.cardId as string;

  // Fetch card data
  const { data: card, isLoading, error } = useCard(projectSlug, cardId);
  const { data: allCards } = useCards(projectSlug);

  // Mutations
  const updateCard = useUpdateCard(projectSlug, cardId);
  const updateCardSection = useUpdateCardSection(projectSlug, cardId);
  const regenerateSection = useRegenerateCardSection(projectSlug, cardId);
  const draftCardContent = useDraftCardContent(projectSlug, cardId);
  const updateDependencies = useUpdateCardDependencies(projectSlug, cardId);

  // Local state for form
  const [formData, setFormData] = useState({
    title: '',
    story_points: 0,
    priority: Priority.MEDIUM,
    status: CardStatus.DRAFT,
    human_gate: false,
    context_md: '',
    task_md: '',
    outputs_md: '',
    acceptance_criteria_md: '',
    human_gate_checklist_md: '',
  });

  // Dirty tracking per section
  const [dirtyFields, setDirtyFields] = useState<Set<string>>(new Set());
  const debounceRefs = useRef<Record<string, NodeJS.Timeout | null>>({});

  // Initialize form when card loads
  useEffect(() => {
    if (card) {
      setFormData({
        title: card.title,
        story_points: card.story_points || 0,
        priority: card.priority || Priority.MEDIUM,
        status: card.status,
        human_gate: card.human_gate,
        context_md: card.context_md || '',
        task_md: card.task_md || '',
        outputs_md: card.outputs_md || '',
        acceptance_criteria_md: card.acceptance_criteria_md || '',
        human_gate_checklist_md: card.human_gate_checklist_md || '',
      });
      setDirtyFields(new Set());
    }
  }, [card]);

  // Debounced save for sections
  const saveSection = useCallback(
    async (section: string, content: string) => {
      try {
        await updateCardSection.mutateAsync({ section, content });
        setDirtyFields((prev) => {
          const next = new Set(prev);
          next.delete(section);
          return next;
        });
      } catch (error) {
        console.error('Failed to save section:', error);
      }
    },
    [updateCardSection]
  );

  const debouncedSaveSection = useCallback(
    (section: string, content: string) => {
      if (debounceRefs.current[section]) {
        clearTimeout(debounceRefs.current[section]!);
      }
      debounceRefs.current[section] = setTimeout(() => {
        saveSection(section, content);
      }, DEBOUNCE_DELAY);
    },
    [saveSection]
  );

  // Debounced save for metadata
  const saveMetadata = useCallback(
    async (data: Partial<typeof formData>) => {
      try {
        await updateCard.mutateAsync(data);
        setDirtyFields((prev) => {
          const next = new Set(prev);
          Object.keys(data).forEach((key) => next.delete(key));
          return next;
        });
      } catch (error) {
        console.error('Failed to save metadata:', error);
      }
    },
    [updateCard]
  );

  const debouncedSaveMetadata = useCallback(
    (data: Partial<typeof formData>) => {
      if (debounceRefs.current['metadata']) {
        clearTimeout(debounceRefs.current['metadata']!);
      }
      debounceRefs.current['metadata'] = setTimeout(() => {
        saveMetadata(data);
      }, DEBOUNCE_DELAY);
    },
    [saveMetadata]
  );

  // Handle section changes
  const updateSection = useCallback(
    (section: string, content: string) => {
      setFormData((prev) => ({ ...prev, [`${section}_md`]: content }));
      setDirtyFields((prev) => new Set(prev).add(section));
      debouncedSaveSection(section, content);
    },
    [debouncedSaveSection]
  );

  // Handle metadata changes
  const updateMetadata = useCallback(
    <K extends keyof typeof formData>(field: K, value: (typeof formData)[K]) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      setDirtyFields((prev) => new Set(prev).add(field));
      debouncedSaveMetadata({ [field]: value });
    },
    [debouncedSaveMetadata]
  );

  // Handle regenerate section
  const handleRegenerateSection = useCallback(
    async (section: string) => {
      try {
        const result = await regenerateSection.mutateAsync(section);
        setFormData((prev) => ({ ...prev, [`${section}_md`]: result.content }));
        setDirtyFields((prev) => {
          const next = new Set(prev);
          next.delete(section);
          return next;
        });
      } catch (error) {
        console.error('Failed to regenerate section:', error);
      }
    },
    [regenerateSection]
  );

  // Handle draft all sections
  const handleDraftAll = useCallback(async () => {
    try {
      const result = await draftCardContent.mutateAsync();
      setFormData((prev) => ({
        ...prev,
        context_md: result.card.context_md || '',
        task_md: result.card.task_md || '',
        outputs_md: result.card.outputs_md || '',
        acceptance_criteria_md: result.card.acceptance_criteria_md || '',
        human_gate_checklist_md: result.card.human_gate_checklist_md || '',
      }));
      setDirtyFields(new Set());
    } catch (error) {
      console.error('Failed to draft card:', error);
    }
  }, [draftCardContent]);

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      Object.values(debounceRefs.current).forEach((timeout) => {
        if (timeout) clearTimeout(timeout);
      });
    };
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !card) {
    return (
      <div className="flex flex-col items-center justify-center h-[50vh] gap-4">
        <p className="text-muted-foreground">
          {error ? 'Failed to load card' : 'Card not found'}
        </p>
        <Button variant="outline" onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Go Back
        </Button>
      </div>
    );
  }

  const isSaving = updateCard.isPending || updateCardSection.isPending;
  const isRegenerating = regenerateSection.isPending || draftCardContent.isPending;

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push(`/projects/${projectSlug}/backlog` as any)}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Backlog
          </Button>
          <div className="h-6 w-px bg-border" />
          <div>
            <span className="text-sm text-muted-foreground font-mono">{card.code}</span>
            <h1 className="text-2xl font-bold">{card.title}</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {dirtyFields.size > 0 && (
            <span className="text-sm text-muted-foreground">Saving...</span>
          )}
          {isSaving && <Loader2 className="h-4 w-4 animate-spin" />}
          {dirtyFields.size === 0 && !isSaving && (
            <span className="text-sm text-green-600">Saved</span>
          )}
          <Button
            variant="default"
            onClick={handleDraftAll}
            disabled={isRegenerating}
          >
            {draftCardContent.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="mr-2 h-4 w-4" />
            )}
            Draft All Sections
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="sections" className="space-y-4">
        <TabsList>
          <TabsTrigger value="sections">Sections</TabsTrigger>
          <TabsTrigger value="metadata">Metadata</TabsTrigger>
          <TabsTrigger value="dependencies">
            <Link2 className="mr-2 h-4 w-4" />
            Dependencies
          </TabsTrigger>
          <TabsTrigger value="inputs">
            <FileInput className="mr-2 h-4 w-4" />
            Inputs ({card.inputs?.length || 0})
          </TabsTrigger>
          {formData.human_gate && (
            <TabsTrigger value="gate">
              <AlertCircle className="mr-2 h-4 w-4" />
              Human Gate
            </TabsTrigger>
          )}
        </TabsList>

        {/* Sections Tab */}
        <TabsContent value="sections" className="space-y-4">
          {SECTIONS.map((section) => (
            <SectionPane
              key={section.key}
              section={section.key}
              label={section.label}
              icon={section.icon}
              description={section.description}
              value={formData[`${section.key}_md` as keyof typeof formData] as string}
              onChange={(content) => updateSection(section.key, content)}
              onRegenerate={() => handleRegenerateSection(section.key)}
              isRegenerating={regenerateSection.isPending}
              isDirty={dirtyFields.has(section.key)}
            />
          ))}
        </TabsContent>

        {/* Metadata Tab */}
        <TabsContent value="metadata">
          <Card>
            <CardHeader>
              <CardTitle>Card Metadata</CardTitle>
              <CardDescription>
                Basic information about the card. Changes are saved automatically.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="title">Title</Label>
                  <Input
                    id="title"
                    value={formData.title}
                    onChange={(e) => updateMetadata('title', e.target.value)}
                    placeholder="Card title"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="story_points">Story Points</Label>
                  <Input
                    id="story_points"
                    type="number"
                    min={0}
                    value={formData.story_points}
                    onChange={(e) => updateMetadata('story_points', parseInt(e.target.value) || 0)}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="priority">Priority</Label>
                  <Select
                    value={formData.priority}
                    onValueChange={(value) => updateMetadata('priority', value as Priority)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PRIORITY_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="status">Status</Label>
                  <Select
                    value={formData.status}
                    onValueChange={(value) => updateMetadata('status', value as CardStatus)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUS_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex items-center justify-between rounded-lg border p-4">
                <div className="space-y-0.5">
                  <Label htmlFor="human_gate">Human Gate</Label>
                  <p className="text-sm text-muted-foreground">
                    Require human approval before proceeding to next card
                  </p>
                </div>
                <Checkbox
                  id="human_gate"
                  checked={formData.human_gate}
                  onCheckedChange={(checked: boolean) => updateMetadata('human_gate', checked)}
                />
              </div>
              <div className="text-xs text-muted-foreground space-x-4">
                <span>Code: <code className="bg-muted px-1 rounded">{card.code}</code></span>
                <span>Type: <code className="bg-muted px-1 rounded">{card.type}</code></span>
                <span>Skills: {card.skill_slugs?.join(', ') || 'None'}</span>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Dependencies Tab */}
        <TabsContent value="dependencies">
          <Card>
            <CardHeader>
              <CardTitle>Card Dependencies</CardTitle>
              <CardDescription>
                Define which cards must be completed before this one, or can run in parallel.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CardDependenciesEditor
                projectSlug={projectSlug}
                cardId={cardId}
                currentCard={card}
                allCards={allCards || []}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Inputs Tab */}
        <TabsContent value="inputs">
          <Card>
            <CardHeader>
              <CardTitle>Card Inputs</CardTitle>
              <CardDescription>
                Define inputs required for this card (skill resources, artifacts, external files).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CardInputsEditor
                projectSlug={projectSlug}
                cardId={cardId}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Human Gate Tab */}
        {formData.human_gate && (
          <TabsContent value="gate">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Human Gate Checklist</CardTitle>
                    <CardDescription>
                      Checklist items that must be verified before proceeding. Markdown format.
                    </CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    onClick={() => handleRegenerateSection('human_gate_checklist')}
                    disabled={regenerateSection.isPending}
                  >
                    {regenerateSection.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="mr-2 h-4 w-4" />
                    )}
                    Regenerate
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <CodeEditor
                  value={formData.human_gate_checklist_md}
                  onChange={(content) => updateSection('human_gate_checklist', content)}
                  language="markdown"
                  placeholder="- [ ] First item to check&#10;- [ ] Second item to check"
                  minHeight="200px"
                  maxHeight="400px"
                />
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

// Section Pane Component
interface SectionPaneProps {
  section: string;
  label: string;
  icon: React.ElementType;
  description: string;
  value: string;
  onChange: (content: string) => void;
  onRegenerate: () => void;
  isRegenerating: boolean;
  isDirty: boolean;
}

function SectionPane({
  section,
  label,
  icon: Icon,
  description,
  value,
  onChange,
  onRegenerate,
  isRegenerating,
  isDirty,
}: SectionPaneProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className="h-5 w-5 text-muted-foreground" />
            <div>
              <CardTitle className="text-base">{label}</CardTitle>
              <CardDescription className="text-sm">{description}</CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isDirty && <span className="text-xs text-muted-foreground">Saving...</span>}
            <Button
              variant="outline"
              size="sm"
              onClick={onRegenerate}
              disabled={isRegenerating}
            >
              {isRegenerating ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="mr-2 h-4 w-4" />
              )}
              Regenerate
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <CodeEditor
          value={value}
          onChange={onChange}
          language="markdown"
          placeholder={`Write ${label.toLowerCase()} in markdown...`}
          minHeight="150px"
          maxHeight="400px"
        />
      </CardContent>
    </Card>
  );
}
