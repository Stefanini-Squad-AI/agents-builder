'use client';

import { useMemo, useState } from 'react';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Search } from 'lucide-react';
import { CatalogCard } from './catalog-card';
import { useMcpCatalog } from '@/lib/api/queries/use-mcp';
import { MCPCategory, MCPConfigSummary } from '@/lib/api/types';

interface CatalogBrowserProps {
  configs: MCPConfigSummary[] | undefined;
  onConfigure: (key: string) => void;
}

const CATEGORY_OPTIONS: { value: 'all' | MCPCategory; label: string }[] = [
  { value: 'all', label: 'All categories' },
  { value: 'source_control', label: 'Source control' },
  { value: 'database', label: 'Database' },
  { value: 'project_management', label: 'Project management' },
  { value: 'documentation', label: 'Documentation' },
  { value: 'messaging', label: 'Messaging' },
  { value: 'monitoring', label: 'Monitoring' },
  { value: 'cloud', label: 'Cloud' },
  { value: 'utility', label: 'Utility' },
];

export function CatalogBrowser({ configs, onConfigure }: CatalogBrowserProps) {
  const [category, setCategory] = useState<'all' | MCPCategory>('all');
  const [search, setSearch] = useState('');

  const { data: catalog, isLoading, error } = useMcpCatalog(
    category === 'all' ? undefined : category
  );

  const configuredKeys = useMemo(
    () => new Set((configs ?? []).map((c) => c.mcp_key)),
    [configs]
  );

  const filtered = useMemo(() => {
    if (!catalog) return [];
    const term = search.trim().toLowerCase();
    if (!term) return catalog;
    return catalog.filter(
      (entry) =>
        entry.name.toLowerCase().includes(term) ||
        entry.key.toLowerCase().includes(term) ||
        entry.vendor.toLowerCase().includes(term) ||
        entry.description.toLowerCase().includes(term)
    );
  }, [catalog, search]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search MCPs by name, vendor, or description"
            className="pl-9"
          />
        </div>
        <Select
          value={category}
          onValueChange={(v) => setCategory(v as 'all' | MCPCategory)}
        >
          <SelectTrigger className="w-56">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            {CATEGORY_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          Failed to load catalog: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-48 w-full rounded-lg" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">
          No MCPs match your search.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((entry) => (
            <CatalogCard
              key={entry.key}
              entry={entry}
              isConfigured={configuredKeys.has(entry.key)}
              onConfigure={onConfigure}
            />
          ))}
        </div>
      )}
    </div>
  );
}
