'use client'

import React from 'react'
import { useAuth } from '@/lib/auth/context'
import { useRouteProtection } from '@/lib/auth/hooks'
import { useProjects } from '@/lib/api/queries/use-projects'
import { useSkills } from '@/lib/api/queries/use-skills'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Plus, FolderOpen, Lightbulb, Activity, TrendingUp } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import Link from 'next/link'
import type { ProjectView } from '@/lib/api/types'

function ProjectQuickCard({ project }: { project: ProjectView }) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'draft': return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      case 'ready': return 'bg-green-100 text-green-800 border-green-200'
      case 'complete': return 'bg-blue-100 text-blue-800 border-blue-200'
      default: return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  return (
    <Card className="hover:shadow-md transition-shadow cursor-pointer">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <h4 className="font-semibold text-sm">{project.name}</h4>
            {project.context_md && (
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                {project.context_md.slice(0, 100)}...
              </p>
            )}
            <div className="flex items-center gap-2 mt-3">
              <Badge className={`text-xs ${getStatusColor(project.status)}`}>
                {project.status}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {formatDistanceToNow(new Date(project.updated_at), { addSuffix: true })}
              </span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function DashboardPage() {
  useRouteProtection() // Ensure user is authenticated
  const { user } = useAuth()
  const { data: projects, isLoading: projectsLoading } = useProjects()
  // TODO: Implement global skills query - current useSkills requires projectSlug
  const skills: any[] = []
  const skillsLoading = false

  const stats = React.useMemo(() => {
    if (!projects) return { total: 0, draft: 0, ready: 0, complete: 0 }
    
    return {
      total: projects.length,
      draft: projects.filter(p => p.status === 'draft').length,
      ready: projects.filter(p => p.status === 'in_progress').length,
      complete: projects.filter(p => p.status === 'exported').length,
    }
  }, [projects])

  const recentProjects = React.useMemo(() => {
    if (!projects) return []
    return [...projects]
      .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
      .slice(0, 6)
  }, [projects])

  if (!user) {
    return null // Will redirect via useRouteProtection
  }

  return (
    <div className="container mx-auto py-8 space-y-8">
      {/* Welcome Header */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">
          Welcome back, {user.name || user.email}
        </h1>
        <p className="text-muted-foreground">
          Here&apos;s an overview of your AI agent projects and workflows
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Projects</CardTitle>
            <FolderOpen className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {projectsLoading ? '...' : stats.total}
            </div>
            <p className="text-xs text-muted-foreground">
              All your projects
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">In Progress</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {projectsLoading ? '...' : stats.draft + stats.ready}
            </div>
            <p className="text-xs text-muted-foreground">
              Draft and ready projects
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {projectsLoading ? '...' : stats.complete}
            </div>
            <p className="text-xs text-muted-foreground">
              Finished projects
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Skills</CardTitle>
            <Lightbulb className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {skillsLoading ? '...' : skills?.length || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Reusable skills
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            <Link href="/projects">
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                New Project
              </Button>
            </Link>
            <Link href="/projects">
              <Button variant="outline">
                <FolderOpen className="mr-2 h-4 w-4" />
                View All Projects
              </Button>
            </Link>
            <Button variant="outline" onClick={() => window.location.href = '/skills'}>
              <Lightbulb className="mr-2 h-4 w-4" />
              Manage Skills
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Recent Projects */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Recent Projects</CardTitle>
          <Link href="/projects">
            <Button variant="ghost" size="sm">
              View All
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          {projectsLoading ? (
            <div className="text-center py-8 text-muted-foreground">
              Loading projects...
            </div>
          ) : recentProjects.length === 0 ? (
            <div className="text-center py-8 space-y-3">
              <div className="text-muted-foreground">No projects yet</div>
              <Link href="/projects">
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  Create Your First Project
                </Button>
              </Link>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {recentProjects.map((project) => (
                <Link key={project.id} href={`/projects/${project.slug}` as any}>
                  <ProjectQuickCard project={project} />
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Debug Info (Development) */}
      {process.env.NODE_ENV === 'development' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Development Info</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs space-y-1">
              <div><strong>User:</strong> {user.email} (Role: {user.role}, Tenant: {user.tenant_id})</div>
              <div><strong>Projects:</strong> {projects?.length || 0} loaded</div>
              <div><strong>Skills:</strong> {skills?.length || 0} loaded</div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}