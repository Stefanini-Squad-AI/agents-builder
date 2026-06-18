'use client';

import Link from 'next/link';
import { useProjects } from '@/lib/api/queries';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Lightbulb, FolderOpen, Loader2 } from 'lucide-react';

export default function SkillsPage() {
  const { data: projects, isLoading } = useProjects();

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="container mx-auto py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Skills</h1>
        <p className="text-muted-foreground mt-2">
          Skills are project-specific. Select a project to view and manage its skills.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {projects?.map((project) => (
          <Link key={project.id} href={`/projects/${project.slug}/skills`}>
            <Card className="hover:border-primary/50 hover:shadow-md transition-all cursor-pointer h-full">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <Lightbulb className="h-5 w-5 text-muted-foreground" />
                  <CardTitle className="text-lg">{project.name}</CardTitle>
                </div>
                <CardDescription className="text-xs font-mono">
                  {project.slug}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {project.objective || 'No description'}
                </p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {(!projects || projects.length === 0) && (
        <div className="text-center py-12">
          <FolderOpen className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold">No projects yet</h3>
          <p className="text-muted-foreground mb-4">Create a project to start managing skills.</p>
          <Button asChild>
            <Link href="/projects">Go to Projects</Link>
          </Button>
        </div>
      )}
    </div>
  );
}
