'use client'

import React, { useEffect } from 'react'
import Link from 'next/link'
import { Plus, Search, Filter, MoreHorizontal, Edit, Trash2, ExternalLink } from 'lucide-react'
import { useProjects } from '@/lib/api/queries/use-projects'
import { useProjectStore } from '@/lib/store/project-store'
import { ProjectCreateDialog } from '@/components/projects/project-create-dialog'
import { ProjectEditDialog } from '@/components/projects/project-edit-dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { formatDistanceToNow } from 'date-fns'
import type { ProjectView } from '@/lib/api/types'

const getStatusBadgeVariant = (status: string) => {
  switch (status) {
    case 'draft': return 'secondary'
    case 'ready': return 'default'
    case 'complete': return 'outline'
    default: return 'secondary'
  }
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'draft': return 'text-yellow-600'
    case 'ready': return 'text-green-600'
    case 'complete': return 'text-blue-600'
    default: return 'text-gray-600'
  }
}

export default function ProjectsPage() {
  const { data: projects, isLoading, error } = useProjects()
  const {
    searchTerm,
    setSearchTerm,
    statusFilter,
    setStatusFilter,
    setProjects,
    setCurrentProject,
    isCreating,
    setIsCreating,
    isEditing,
    setIsEditing,
    currentProject,
  } = useProjectStore()

  // Update store when projects are loaded
  useEffect(() => {
    if (projects) {
      setProjects(projects)
    }
  }, [projects, setProjects])

  const filteredProjects = React.useMemo(() => {
    if (!projects) return []
    
    return projects.filter((project: ProjectView) => {
      const matchesSearch = project.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          project.context_md?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          project.objective?.toLowerCase().includes(searchTerm.toLowerCase())
      const matchesStatus = statusFilter === 'all' || project.status === statusFilter
      
      return matchesSearch && matchesStatus
    })
  }, [projects, searchTerm, statusFilter])

  const handleEditProject = (project: ProjectView) => {
    setCurrentProject(project)
    setIsEditing(true)
  }

  const handleDeleteProject = (project: ProjectView) => {
    // TODO: Add delete confirmation dialog and implement delete
    console.log('Delete project:', project.id)
  }

  if (error) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardContent className="p-6">
            <div className="text-center text-red-600">
              Error loading projects: {error.message}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="container mx-auto py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Projects</h1>
          <p className="text-muted-foreground">
            Manage your AI agent projects and workflows
          </p>
        </div>
        <Button onClick={() => setIsCreating(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Project
        </Button>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search projects..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex gap-2">
              <Button
                variant={statusFilter === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setStatusFilter('all')}
              >
                All
              </Button>
              <Button
                variant={statusFilter === 'draft' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setStatusFilter('draft')}
              >
                Draft
              </Button>
              <Button
                variant={statusFilter === 'ready' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setStatusFilter('ready')}
              >
                Ready
              </Button>
              <Button
                variant={statusFilter === 'complete' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setStatusFilter('complete')}
              >
                Complete
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Projects Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            {filteredProjects.length} project{filteredProjects.length !== 1 ? 's' : ''}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">
              Loading projects...
            </div>
          ) : filteredProjects.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {searchTerm || statusFilter !== 'all' ? 'No projects match your filters' : 'No projects yet'}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Objective</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="w-[70px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredProjects.map((project: ProjectView) => (
                  <TableRow key={project.id} className="cursor-pointer hover:bg-muted/50">
                    <TableCell>
                      <Link href={`/projects/${project.slug}`} className="block">
                        <div className="font-medium text-primary hover:underline">{project.name}</div>
                        {project.context_md && (
                          <div className="text-sm text-muted-foreground line-clamp-1">
                            {project.context_md.slice(0, 50)}...
                          </div>
                        )}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant={getStatusBadgeVariant(project.status)}>
                        {project.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="max-w-[300px] text-sm text-muted-foreground line-clamp-2">
                        {project.objective || 'No objective set'}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm text-muted-foreground">
                        {formatDistanceToNow(new Date(project.updated_at), { addSuffix: true })}
                      </div>
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem asChild>
                            <Link href={`/projects/${project.slug}`}>
                              <ExternalLink className="mr-2 h-4 w-4" />
                              Open
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleEditProject(project)}>
                            <Edit className="mr-2 h-4 w-4" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem 
                            onClick={() => handleDeleteProject(project)}
                            className="text-red-600"
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Dialogs */}
      <ProjectCreateDialog open={isCreating} onOpenChange={setIsCreating} />
      <ProjectEditDialog 
        open={isEditing} 
        onOpenChange={setIsEditing}
        project={currentProject}
      />
    </div>
  )
}