"use client"

import { useProjects } from '@/lib/api/queries'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

export function ProjectsDemo() {
  const { data: projects, isLoading, error, refetch } = useProjects()

  if (isLoading) {
    return (
      <div className="rounded-lg border p-4">
        <h3 className="font-semibold mb-2">Projects (Loading...)</h3>
        <div className="animate-pulse">
          <div className="h-4 bg-muted rounded mb-2"></div>
          <div className="h-4 bg-muted rounded w-2/3"></div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border p-4">
        <h3 className="font-semibold mb-2 text-destructive">Projects (Error)</h3>
        <p className="text-sm text-muted-foreground mb-2">
          {error.message || 'Failed to load projects'}
        </p>
        <Button size="sm" variant="outline" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="rounded-lg border p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold">Projects</h3>
        <Badge variant="secondary">{projects?.length || 0}</Badge>
      </div>
      
      {!projects || projects.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No projects found. The API is connected but no projects exist yet.
        </p>
      ) : (
        <div className="space-y-2">
          {projects.slice(0, 3).map((project) => (
            <div key={project.id} className="flex items-center justify-between">
              <div>
                <p className="font-medium text-sm">{project.name}</p>
                <p className="text-xs text-muted-foreground">{project.slug}</p>
              </div>
              <Badge variant="outline">{project.status}</Badge>
            </div>
          ))}
          {projects.length > 3 && (
            <p className="text-xs text-muted-foreground">
              +{projects.length - 3} more projects
            </p>
          )}
        </div>
      )}
      
      <Button 
        size="sm" 
        variant="ghost" 
        onClick={() => refetch()}
        className="mt-2"
      >
        Refresh
      </Button>
    </div>
  )
}