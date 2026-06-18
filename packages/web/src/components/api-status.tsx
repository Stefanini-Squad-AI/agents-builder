"use client"

import { useQuery } from '@tanstack/react-query'
import { healthCheck } from '@/lib/api/client'
import { Badge } from '@/components/ui/badge'

interface ApiStatusProps {
  className?: string
}

export function ApiStatus({ className }: ApiStatusProps) {
  const { data: isHealthy, isLoading, error } = useQuery({
    queryKey: ['api-health'],
    queryFn: () => healthCheck(),
    refetchInterval: 30000, // Check every 30 seconds
    retry: 1,
  })

  if (isLoading) {
    return (
      <Badge variant="secondary" className={className}>
        Checking API...
      </Badge>
    )
  }

  if (error || !isHealthy) {
    return (
      <Badge variant="destructive" className={className}>
        API Offline
      </Badge>
    )
  }

  return (
    <Badge variant="default" className={className}>
      API Connected
    </Badge>
  )
}