'use client'

import React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2 } from 'lucide-react'
import { useCreateProject } from '@/lib/api/queries/use-projects'
import { useProjectStore } from '@/lib/store/project-store'
import { CardTemplate, LlmProvider, ProjectType } from '@/lib/api/types'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const LLM_MODELS: Record<LlmProvider, string[]> = {
  [LlmProvider.ANTHROPIC]: ['claude-sonnet-4-5', 'claude-opus-4', 'claude-3-5-sonnet-20241022', 'claude-3-haiku-20240307'],
  [LlmProvider.OPENAI]: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  [LlmProvider.OLLAMA]: ['llama3.2', 'llama3.1', 'codellama', 'mistral'],
  [LlmProvider.BEDROCK]: [
    'us.anthropic.claude-sonnet-4-20250514-v1:0',
    'us.anthropic.claude-haiku-4-20250514-v1:0',
    'anthropic.claude-3-5-sonnet-20241022-v2:0',
    'anthropic.claude-3-5-haiku-20241022-v1:0',
    'anthropic.claude-3-sonnet-20240229-v1:0',
    'anthropic.claude-3-haiku-20240307-v1:0',
  ],
}

const projectCreateSchema = z.object({
  name: z.string().min(1, 'Project name is required').max(100, 'Name too long'),
  objective: z.string().min(10, 'Objective must be at least 10 characters').max(2000, 'Objective too long'),
  card_code_prefix: z
    .string()
    .min(2, 'Code prefix must be at least 2 characters')
    .max(8, 'Code prefix must be at most 8 characters')
    .regex(/^[A-Z0-9]+$/, 'Code prefix must be uppercase letters and numbers only'),
  project_type: z.nativeEnum(ProjectType),
  card_template: z.nativeEnum(CardTemplate),
  llm_provider: z.nativeEnum(LlmProvider),
  llm_model: z.string().min(1, 'Model is required'),
})

type ProjectCreateForm = z.infer<typeof projectCreateSchema>

interface ProjectCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ProjectCreateDialog({ open, onOpenChange }: ProjectCreateDialogProps) {
  const { addProject } = useProjectStore()
  const createProjectMutation = useCreateProject()

  const form = useForm<ProjectCreateForm>({
    resolver: zodResolver(projectCreateSchema),
    defaultValues: {
      name: '',
      objective: '',
      card_code_prefix: '',
      project_type: ProjectType.APPLICATION,
      card_template: CardTemplate.PHASE_VLI,
      llm_provider: LlmProvider.ANTHROPIC,
      llm_model: 'claude-sonnet-4-5',
    },
  })

  const selectedProvider = form.watch('llm_provider')
  const selectedProjectType = form.watch('project_type')
  const isMigration = selectedProjectType === ProjectType.MIGRATION

  // When project type changes, sync card_template accordingly
  React.useEffect(() => {
    if (isMigration) {
      form.setValue('card_template', CardTemplate.MIGRATION)
    } else {
      const current = form.getValues('card_template')
      if (current === CardTemplate.MIGRATION) {
        form.setValue('card_template', CardTemplate.PHASE_VLI)
      }
    }
  }, [isMigration, form])

  // Update model when provider changes
  React.useEffect(() => {
    const models = LLM_MODELS[selectedProvider]
    if (models && models.length > 0) {
      const currentModel = form.getValues('llm_model')
      if (!models.includes(currentModel)) {
        form.setValue('llm_model', models[0])
      }
    }
  }, [selectedProvider, form])

  // Auto-generate code prefix from name
  const handleNameChange = (value: string, onChange: (v: string) => void) => {
    onChange(value)
    // Auto-generate prefix if empty
    if (!form.getValues('card_code_prefix')) {
      const words = value.trim().split(/\s+/)
      let prefix = ''
      if (words.length >= 2) {
        prefix = words.slice(0, 4).map(w => w[0]?.toUpperCase() || '').join('')
      } else if (value.length > 0) {
        prefix = value.slice(0, 4).toUpperCase().replace(/[^A-Z0-9]/g, '')
      }
      if (prefix.length >= 2) {
        form.setValue('card_code_prefix', prefix)
      }
    }
  }

  const onSubmit = async (data: ProjectCreateForm) => {
    try {
      const isMig = data.project_type === ProjectType.MIGRATION
      const newProject = await createProjectMutation.mutateAsync({
        slug: data.name.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
        name: data.name,
        objective: data.objective,
        card_code_prefix: data.card_code_prefix,
        project_type: data.project_type,
        card_template: isMig ? CardTemplate.MIGRATION : data.card_template,
        source_technology: isMig ? 'ssis' : undefined,
        target_technology: isMig ? 'databricks' : undefined,
        llm_provider: data.llm_provider,
        llm_model: data.llm_model,
      })
      
      addProject(newProject)
      form.reset()
      onOpenChange(false)
    } catch (error) {
      console.error('Failed to create project:', error)
      // Error is handled by the mutation and will show in the UI through react-query
    }
  }

  const handleOpenChange = (newOpen: boolean) => {
    if (!createProjectMutation.isPending) {
      if (!newOpen) {
        form.reset()
      }
      onOpenChange(newOpen)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create New Project</DialogTitle>
          <DialogDescription>
            Create a new AI agent project. Configure your project settings and LLM preferences.
          </DialogDescription>
        </DialogHeader>
        
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">

            {/* Project type selector — drives the whole form */}
            <FormField
              control={form.control}
              name="project_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Project Type *</FormLabel>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      {
                        value: ProjectType.APPLICATION,
                        label: 'Application Development',
                        description: 'Skills, backlog, DAG and export workflow',
                      },
                      {
                        value: ProjectType.MIGRATION,
                        label: 'ETL Migration',
                        description: 'SSIS → Databricks · Migration Workbench',
                      },
                    ].map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        disabled={createProjectMutation.isPending}
                        onClick={() => field.onChange(opt.value)}
                        className={[
                          'flex flex-col items-start gap-1 rounded-lg border p-3 text-left transition-colors',
                          field.value === opt.value
                            ? 'border-primary bg-primary/5'
                            : 'border-border hover:border-muted-foreground',
                        ].join(' ')}
                      >
                        <span className="text-sm font-medium">{opt.label}</span>
                        <span className="text-xs text-muted-foreground">{opt.description}</span>
                      </button>
                    ))}
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Project Name *</FormLabel>
                  <FormControl>
                    <Input 
                      placeholder="My AI Agent Project" 
                      {...field}
                      onChange={(e) => handleNameChange(e.target.value, field.onChange)}
                      disabled={createProjectMutation.isPending}
                    />
                  </FormControl>
                  <FormDescription>
                    Choose a clear, descriptive name for your project
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="card_code_prefix"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Card Code Prefix *</FormLabel>
                  <FormControl>
                    <Input 
                      placeholder="PROJ" 
                      {...field}
                      onChange={(e) => field.onChange(e.target.value.toUpperCase())}
                      disabled={createProjectMutation.isPending}
                      className="uppercase"
                      maxLength={8}
                    />
                  </FormControl>
                  <FormDescription>
                    2-8 uppercase letters/numbers used as prefix for card codes (e.g., PROJ-001)
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="objective"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Project Objective *</FormLabel>
                  <FormControl>
                    <Textarea 
                      placeholder="Describe what you want to achieve with this project..."
                      className="min-h-[100px]"
                      {...field} 
                      disabled={createProjectMutation.isPending}
                    />
                  </FormControl>
                  <FormDescription>
                    Describe the main goal or problem this project aims to solve
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-2 gap-4">
              {isMigration ? (
                /* Migration: show locked source → target tech badges */
                <div className="space-y-2">
                  <FormLabel>Technologies</FormLabel>
                  <div className="flex items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-2">
                    <Badge variant="secondary" className="text-xs">SSIS</Badge>
                    <span className="text-xs text-muted-foreground">→</span>
                    <Badge variant="secondary" className="text-xs">Databricks</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Source and target are fixed for this project type
                  </p>
                </div>
              ) : (
                <FormField
                  control={form.control}
                  name="card_template"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Card Template</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value} disabled={createProjectMutation.isPending}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select template" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value={CardTemplate.PHASE_VLI}>Phase VLI (Default)</SelectItem>
                          <SelectItem value={CardTemplate.STRICT_9}>Strict 9 Sections</SelectItem>
                          <SelectItem value={CardTemplate.FREE_FORM}>Free Form</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormDescription>
                        Structure for generated cards
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              <FormField
                control={form.control}
                name="llm_provider"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>LLM Provider</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value} disabled={createProjectMutation.isPending}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select provider" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value={LlmProvider.ANTHROPIC}>Anthropic</SelectItem>
                        <SelectItem value={LlmProvider.OPENAI}>OpenAI</SelectItem>
                        <SelectItem value={LlmProvider.OLLAMA}>Ollama (Local)</SelectItem>
                        <SelectItem value={LlmProvider.BEDROCK}>AWS Bedrock</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      AI provider for generation
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="llm_model"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Model</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value} disabled={createProjectMutation.isPending}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select model" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {LLM_MODELS[selectedProvider]?.map((model) => (
                        <SelectItem key={model} value={model}>
                          {model}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormDescription>
                    Specific model to use for AI generation
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {createProjectMutation.error && (
              <div className="text-sm text-red-600">
                Failed to create project: {createProjectMutation.error.message}
              </div>
            )}

            <div className="flex justify-end space-x-2 pt-4">
              <Button 
                type="button" 
                variant="outline" 
                onClick={() => handleOpenChange(false)}
                disabled={createProjectMutation.isPending}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createProjectMutation.isPending}>
                {createProjectMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Create Project
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}