'use client';

import { useParams, useRouter } from 'next/navigation';
import { useState, useCallback, useEffect, useRef } from 'react';
import { useSkill, useUpdateSkill, useDraftSkillBody } from '@/lib/api/queries';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
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
import { SkillResourcesEditor } from '@/components/skills/skill-resources-editor';
import { SkillKind, UpdateSkillRequest } from '@/lib/api/types';
import { ArrowLeft, Save, Sparkles, Loader2 } from 'lucide-react';

const SKILL_KIND_OPTIONS: { value: SkillKind; label: string }[] = [
  { value: SkillKind.CONTEXT, label: 'Context' },
  { value: SkillKind.ANALYZER, label: 'Analyzer' },
  { value: SkillKind.AUTHORING, label: 'Authoring' },
  { value: SkillKind.PROCEDURE, label: 'Procedure' },
];

const DEBOUNCE_DELAY = 1000;

export default function SkillEditorPage() {
  const params = useParams();
  const router = useRouter();
  const projectSlug = params.slug as string;
  const skillSlug = params.skillSlug as string;

  // Fetch skill data
  const { data: skill, isLoading, error } = useSkill(projectSlug, skillSlug);

  // Mutations
  const updateSkill = useUpdateSkill(projectSlug, skillSlug);
  const draftSkillBody = useDraftSkillBody(projectSlug, skillSlug);

  // Local state for form
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    kind: SkillKind.CONTEXT,
    body_md: '',
  });

  // Dirty tracking for autosave
  const [isDirty, setIsDirty] = useState(false);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize form when skill loads
  useEffect(() => {
    if (skill) {
      setFormData({
        name: skill.name,
        description: skill.description,
        kind: skill.kind,
        body_md: skill.body_md,
      });
      setIsDirty(false);
    }
  }, [skill]);

  // Debounced save
  const saveChanges = useCallback(
    async (data: Partial<UpdateSkillRequest>) => {
      if (!skill) return;
      try {
        await updateSkill.mutateAsync(data);
        setIsDirty(false);
      } catch (error) {
        console.error('Failed to save:', error);
      }
    },
    [skill, updateSkill]
  );

  const debouncedSave = useCallback(
    (data: Partial<UpdateSkillRequest>) => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
      debounceRef.current = setTimeout(() => {
        saveChanges(data);
      }, DEBOUNCE_DELAY);
    },
    [saveChanges]
  );

  // Handle field changes
  const updateField = useCallback(
    <K extends keyof typeof formData>(field: K, value: (typeof formData)[K]) => {
      setFormData((prev) => {
        const updated = { ...prev, [field]: value };
        setIsDirty(true);
        debouncedSave({ [field]: value });
        return updated;
      });
    },
    [debouncedSave]
  );

  // Handle regenerate body
  const handleRegenerateBody = useCallback(async () => {
    try {
      const result = await draftSkillBody.mutateAsync({ include_resources: false });
      setFormData((prev) => ({ ...prev, body_md: result.body_md }));
      setIsDirty(false);
    } catch (error) {
      console.error('Failed to regenerate body:', error);
    }
  }, [draftSkillBody]);

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !skill) {
    return (
      <div className="flex flex-col items-center justify-center h-[50vh] gap-4">
        <p className="text-muted-foreground">
          {error ? 'Failed to load skill' : 'Skill not found'}
        </p>
        <Button variant="outline" onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Go Back
        </Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push(`/projects/${projectSlug}/skills` as any)}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Skills
          </Button>
          <div className="h-6 w-px bg-border" />
          <h1 className="text-2xl font-bold">{skill.name}</h1>
        </div>
        <div className="flex items-center gap-2">
          {isDirty && (
            <span className="text-sm text-muted-foreground">Saving...</span>
          )}
          {updateSkill.isPending && (
            <Loader2 className="h-4 w-4 animate-spin" />
          )}
          {!isDirty && !updateSkill.isPending && (
            <span className="text-sm text-green-600">Saved</span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="frontmatter" className="space-y-4">
        <TabsList>
          <TabsTrigger value="frontmatter">Frontmatter</TabsTrigger>
          <TabsTrigger value="body">Body</TabsTrigger>
          <TabsTrigger value="resources">
            Resources ({skill.resources?.length || 0})
          </TabsTrigger>
        </TabsList>

        {/* Frontmatter Tab */}
        <TabsContent value="frontmatter">
          <Card>
            <CardHeader>
              <CardTitle>Skill Metadata</CardTitle>
              <CardDescription>
                Basic information about the skill. Changes are saved automatically.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Name</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => updateField('name', e.target.value)}
                    placeholder="Skill name"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="kind">Kind</Label>
                  <Select
                    value={formData.kind}
                    onValueChange={(value) => updateField('kind', value as SkillKind)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {SKILL_KIND_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => updateField('description', e.target.value)}
                  placeholder="Describe what this skill does..."
                  rows={4}
                />
              </div>
              <div className="text-xs text-muted-foreground">
                Slug: <code className="bg-muted px-1 rounded">{skill.slug}</code>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Body Tab */}
        <TabsContent value="body">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Skill Body</CardTitle>
                  <CardDescription>
                    The markdown content that defines this skill. Changes are saved automatically.
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  onClick={handleRegenerateBody}
                  disabled={draftSkillBody.isPending}
                >
                  {draftSkillBody.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="mr-2 h-4 w-4" />
                  )}
                  Regenerate Body
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <CodeEditor
                value={formData.body_md}
                onChange={(value) => updateField('body_md', value)}
                language="markdown"
                placeholder="Write skill body in markdown..."
                minHeight="400px"
                maxHeight="600px"
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Resources Tab */}
        <TabsContent value="resources">
          <Card>
            <CardHeader>
              <CardTitle>Skill Resources</CardTitle>
              <CardDescription>
                Additional files attached to this skill (SQL, YAML, Python, etc.)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <SkillResourcesEditor
                projectSlug={projectSlug}
                skillSlug={skillSlug}
                resources={skill.resources || []}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
