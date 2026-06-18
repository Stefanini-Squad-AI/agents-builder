"use client";

import { useWorkerStatus } from "@/lib/api/queries";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Activity, AlertTriangle, XCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface WorkerStatusIndicatorProps {
  className?: string;
  showLabel?: boolean;
}

export function WorkerStatusIndicator({
  className,
  showLabel = false,
}: WorkerStatusIndicatorProps) {
  const { status, isLoading, isError } = useWorkerStatus();

  if (isLoading) {
    return (
      <Badge variant="secondary" className={cn("gap-1", className)}>
        <Loader2 className="h-3 w-3 animate-spin" />
        {showLabel && <span>Checking...</span>}
      </Badge>
    );
  }

  if (isError || !status) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant="secondary" className={cn("gap-1 cursor-help", className)}>
              <XCircle className="h-3 w-3" />
              {showLabel && <span>Unknown</span>}
            </Badge>
          </TooltipTrigger>
          <TooltipContent>
            <p>Could not check worker status</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  // Status-based rendering
  const statusConfig = {
    healthy: {
      variant: "default" as const,
      icon: Activity,
      label: "Workers Running",
      description: `${status.workers_detected} worker(s) active, ${status.pending_jobs} pending job(s)`,
      iconClass: "text-green-500",
    },
    no_workers: {
      variant: "outline" as const,
      icon: AlertTriangle,
      label: "No Workers",
      description: `No workers detected. ${status.pending_jobs} job(s) waiting. Run: uv run python -m dramatiq app.jobs`,
      iconClass: "text-yellow-500",
    },
    redis_down: {
      variant: "destructive" as const,
      icon: XCircle,
      label: "Redis Down",
      description: status.error || "Redis is not reachable. Job processing is unavailable.",
      iconClass: "",
    },
  };

  const config = statusConfig[status.status];
  const Icon = config.icon;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant={config.variant}
            className={cn("gap-1 cursor-help", className)}
          >
            <Icon className={cn("h-3 w-3", config.iconClass)} />
            {showLabel && <span>{config.label}</span>}
          </Badge>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-xs">
          <div className="space-y-1">
            <p className="font-medium">{config.label}</p>
            <p className="text-xs text-muted-foreground">{config.description}</p>
            {status.pending_jobs > 0 && status.status !== "healthy" && (
              <p className="text-xs text-yellow-600 dark:text-yellow-400">
                ⚠ {status.pending_jobs} job(s) waiting in queue
              </p>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
