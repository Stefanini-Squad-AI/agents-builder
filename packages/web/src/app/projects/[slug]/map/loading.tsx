import { Loader2 } from 'lucide-react';

export default function MapLoading() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-muted-foreground">Loading migration map...</p>
      </div>
    </div>
  );
}
