'use client';

import { SkillView, SkillKind } from '@/lib/api/types';
import { SkillCard } from './skill-card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Search, FolderOpen } from 'lucide-react';
import { useState, useMemo } from 'react';

interface SkillGridProps {
  skills: SkillView[];
  projectSlug?: string;
  isLoading?: boolean;
  onSkillClick?: (skill: SkillView) => void;
  onSkillEdit?: (skill: SkillView) => void;
  onSkillDelete?: (skill: SkillView) => void;
  deletingSkillSlug?: string | null;
}

/**
 * Grid display of skills with filtering and search
 */
export function SkillGrid({
  skills,
  projectSlug,
  isLoading = false,
  onSkillClick,
  onSkillEdit,
  onSkillDelete,
  deletingSkillSlug,
}: SkillGridProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [kindFilter, setKindFilter] = useState<string>('all');

  // Filter skills based on search and kind
  const filteredSkills = useMemo(() => {
    return skills.filter((skill) => {
      // Kind filter
      if (kindFilter !== 'all' && skill.kind !== kindFilter) {
        return false;
      }

      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        return (
          skill.name.toLowerCase().includes(query) ||
          skill.slug.toLowerCase().includes(query) ||
          skill.description.toLowerCase().includes(query)
        );
      }

      return true;
    });
  }, [skills, searchQuery, kindFilter]);

  // Group skills by kind for display
  const skillsByKind = useMemo(() => {
    const grouped: Record<string, SkillView[]> = {
      [SkillKind.CONTEXT]: [],
      [SkillKind.ANALYZER]: [],
      [SkillKind.AUTHORING]: [],
      [SkillKind.PROCEDURE]: [],
    };

    filteredSkills.forEach((skill) => {
      if (grouped[skill.kind]) {
        grouped[skill.kind].push(skill);
      }
    });

    return grouped;
  }, [filteredSkills]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        {/* Search skeleton */}
        <div className="flex gap-4">
          <Skeleton className="h-10 flex-1" />
          <Skeleton className="h-10 w-40" />
        </div>
        {/* Grid skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      </div>
    );
  }

  if (skills.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <FolderOpen className="h-16 w-16 text-muted-foreground/40 mb-4" />
        <h3 className="text-lg font-semibold">No skills yet</h3>
        <p className="text-muted-foreground max-w-sm">
          Use the &quot;Propose Skill Set&quot; button to generate skills based on your
          project context, or create skills manually.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search skills..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={kindFilter} onValueChange={setKindFilter}>
          <SelectTrigger className="w-full sm:w-40">
            <SelectValue placeholder="Filter by kind" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All kinds</SelectItem>
            <SelectItem value={SkillKind.CONTEXT}>Context</SelectItem>
            <SelectItem value={SkillKind.ANALYZER}>Analyzer</SelectItem>
            <SelectItem value={SkillKind.AUTHORING}>Authoring</SelectItem>
            <SelectItem value={SkillKind.PROCEDURE}>Procedure</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Results count */}
      {(searchQuery || kindFilter !== 'all') && (
        <p className="text-sm text-muted-foreground">
          Showing {filteredSkills.length} of {skills.length} skills
        </p>
      )}

      {/* No results */}
      {filteredSkills.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Search className="h-12 w-12 text-muted-foreground/40 mb-4" />
          <h3 className="text-lg font-semibold">No matching skills</h3>
          <p className="text-muted-foreground">
            Try adjusting your search or filter criteria
          </p>
          <Button
            variant="outline"
            className="mt-4"
            onClick={() => {
              setSearchQuery('');
              setKindFilter('all');
            }}
          >
            Clear filters
          </Button>
        </div>
      )}

      {/* Grid */}
      {filteredSkills.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredSkills.map((skill) => (
            <SkillCard
              key={skill.id}
              skill={skill}
              projectSlug={projectSlug}
              onClick={onSkillClick}
              onEdit={onSkillEdit}
              onDelete={onSkillDelete}
              isDeleting={deletingSkillSlug === skill.slug}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default SkillGrid;
