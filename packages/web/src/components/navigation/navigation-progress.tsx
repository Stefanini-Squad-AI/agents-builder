'use client'

import { useEffect, useState, useRef } from 'react'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'

/**
 * Navigation progress bar that shows when navigating between pages.
 * Shows a loading bar at the top of the screen, dark overlay, and centered tooltip during page transitions.
 */
export function NavigationProgress() {
  const pathname = usePathname()
  const [isNavigating, setIsNavigating] = useState(false)
  const [progress, setProgress] = useState(0)
  const prevPathnameRef = useRef(pathname)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Cleanup function to clear all timers
  const cleanup = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
  }

  // Reset progress when navigation completes (pathname changes)
  useEffect(() => {
    if (pathname !== prevPathnameRef.current) {
      // Navigation completed - cleanup and reset
      cleanup()
      prevPathnameRef.current = pathname
      setProgress(100)
      
      // Fade out after completing
      const fadeTimer = setTimeout(() => {
        setIsNavigating(false)
        setProgress(0)
      }, 200)
      
      return () => clearTimeout(fadeTimer)
    }
  }, [pathname])

  // Cleanup on unmount
  useEffect(() => {
    return cleanup
  }, [])

  // Handle link clicks to start progress
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      const anchor = target.closest('a')
      
      if (!anchor) return
      
      const href = anchor.getAttribute('href')
      if (!href) return
      
      // Skip external links, hash links, and special links
      if (
        href.startsWith('http') ||
        href.startsWith('#') ||
        href.startsWith('mailto:') ||
        href.startsWith('tel:') ||
        href.startsWith('blob:') ||
        href.startsWith('javascript:')
      ) {
        return
      }
      
      // Skip if it's the current page (exact match or with trailing slash)
      const currentPath = prevPathnameRef.current
      if (href === currentPath || href === currentPath + '/' || href + '/' === currentPath) {
        return
      }
      
      // Skip if target is _blank
      if (anchor.getAttribute('target') === '_blank') {
        return
      }
      
      // Cleanup any existing timers
      cleanup()
      
      // Start loading animation
      setIsNavigating(true)
      setProgress(10)
      
      // Simulate progress
      intervalRef.current = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) {
            return 90 // Cap at 90 until navigation completes
          }
          return prev + Math.random() * 10
        })
      }, 200)
      
      // Safety timeout - auto-hide after 10 seconds if navigation never completes
      timeoutRef.current = setTimeout(() => {
        cleanup()
        setIsNavigating(false)
        setProgress(0)
      }, 10000)
    }
    
    document.addEventListener('click', handleClick)
    
    return () => {
      document.removeEventListener('click', handleClick)
    }
  }, [])

  if (!isNavigating && progress === 0) {
    return null
  }

  return (
    <>
      {/* Dark overlay */}
      {isNavigating && (
        <div 
          className="fixed inset-0 bg-black/20 z-[98] pointer-events-none animate-in fade-in duration-150"
          aria-hidden="true"
        />
      )}
      
      {/* Progress bar at top */}
      <div className="fixed top-0 left-0 right-0 z-[100] h-1 bg-transparent pointer-events-none">
        <div
          className={cn(
            'h-full bg-primary transition-all duration-200 ease-out',
            !isNavigating && progress >= 100 && 'opacity-0'
          )}
          style={{ width: `${Math.min(progress, 100)}%` }}
        />
      </div>
      
      {/* Centered loading tooltip */}
      {isNavigating && (
        <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[100] pointer-events-none">
          <div className="flex items-center gap-2 bg-background/95 backdrop-blur px-4 py-2 rounded-lg shadow-lg border animate-in fade-in zoom-in-95 duration-150">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            <span className="text-sm text-muted-foreground">Loading...</span>
          </div>
        </div>
      )}
    </>
  )
}
