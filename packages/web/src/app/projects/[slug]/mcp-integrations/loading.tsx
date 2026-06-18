import { Skeleton } from '@/components/ui/skeleton';

export default function McpIntegrationsLoading() {
  return (
    <div className="container mx-auto space-y-6 py-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-9 w-32" />
        <div className="h-6 w-px bg-border" />
        <Skeleton className="h-6 w-48" />
      </div>

      <Skeleton className="h-10 w-80 rounded" />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[...Array(6)].map((_, i) => (
          <Skeleton key={i} className="h-48 w-full rounded-lg" />
        ))}
      </div>
    </div>
  );
}
