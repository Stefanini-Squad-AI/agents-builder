'use client'

import React, { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2 } from 'lucide-react'
import { useUpdateProject } from '@/lib/api/queries/use-projects'
import { useProjectStore } from '@/lib/store/project-store'
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
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import type { ProjectView } from '@/lib/api/types'

const projectEditSchema = z.object({
  name: z.string().min(1, 'Project name is required').max(100, 'Name too long'),
  objective: z.string().min(10, 'Objective must be at least 10 characters').max(1000, 'Objective too long'),
})

type ProjectEditForm = z.infer<typeof projectEditSchema>

interface ProjectEditDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  project: ProjectView | null
}

export function ProjectEditDialog({ open, onOpenChange, project }: ProjectEditDialogProps) {
  const { updateProject } = useProjectStore()
  const updateProjectMutation = useUpdateProject(project?.slug || '')

  const form = useForm<ProjectEditForm>({
    resolver: zodResolver(projectEditSchema),
    defaultValues: {
      name: '',
      objective: '',
    },
  })

  // Update form when project changes
  useEffect(() => {
    if (project) {
      form.reset({
        name: project.name,
        objective: project.objective || '',
      })
    }
  }, [project, form])

  const onSubmit = async (data: ProjectEditForm) => {
    if (!project) return

    try {
      const updatedProject = await updateProjectMutation.mutateAsync({
        name: data.name,
        objective: data.objective,
      })
      
      updateProject(project.id, updatedProject)
      onOpenChange(false)
    } catch (error) {
      console.error('Failed to update project:', error)
      // Error is handled by the mutation and will show in the UI through react-query
    }
  }

  const handleOpenChange = (newOpen: boolean) => {
    if (!updateProjectMutation.isPending) {
      onOpenChange(newOpen)
    }
  }

  if (!project) return null

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Edit Project</DialogTitle>
          <DialogDescription>
            Update your project information. Changes will be saved immediately.
          </DialogDescription>
        </DialogHeader>
        
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
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
                      disabled={updateProjectMutation.isPending}
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
              name="objective"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Project Objective *</FormLabel>
                  <FormControl>
                    <Textarea 
                      placeholder="Describe what you want to achieve with this project..."
                      className="min-h-[100px]"
                      {...field} 
                      disabled={updateProjectMutation.isPending}
                    />
                  </FormControl>
                  <FormDescription>
                    Describe the main goal or problem this project aims to solve
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {updateProjectMutation.error && (
              <div className="text-sm text-red-600">
                Failed to update project: {updateProjectMutation.error.message}
              </div>
            )}

            <div className="flex justify-end space-x-2 pt-4">
              <Button 
                type="button" 
                variant="outline" 
                onClick={() => handleOpenChange(false)}
                disabled={updateProjectMutation.isPending}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={updateProjectMutation.isPending}>
                {updateProjectMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Save Changes
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}